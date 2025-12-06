<template>
  <div class="codehub-container layout-container">
    <HeaderComponent title="代码仓库" :loading="loading">
      <template #left v-if="showBackButton">
        <a-button type="text" @click="handleBack">
          <ArrowLeft size="16" />
          返回聊天
        </a-button>
      </template>
      <template #description>
        <p>查看和管理通过 git clone 下载的代码仓库</p>
      </template>
    </HeaderComponent>

    <!-- 加载状态 -->
    <div v-if="loading && !selectedRepo" class="loading-container">
      <a-spin size="large" />
      <p>正在加载仓库列表...</p>
    </div>

    <!-- 仓库列表视图 -->
    <div v-else-if="!selectedRepo" class="repositories-list">
      <div v-if="repositories.length === 0" class="empty-state">
        <div class="empty-icon">
          <FolderGit2 size="64" />
        </div>
        <h3>还没有代码仓库</h3>
        <p>使用 git clone 工具克隆仓库后，会在这里显示</p>
      </div>
      <div v-else class="repositories-grid">
        <div
          v-for="repo in repositories"
          :key="repo.name"
          class="repo-card"
          @click="selectRepository(repo.name)"
        >
          <div class="repo-header">
            <FolderGit2 class="repo-icon" />
            <h3>{{ repo.name }}</h3>
          </div>
          <div class="repo-info">
            <a-tag v-if="repo.is_git_repo" color="blue">Git仓库</a-tag>
            <span v-if="repo.remote_url" class="repo-url">{{ repo.remote_url }}</span>
          </div>
          <div class="repo-actions">
            <a-button
              type="text"
              danger
              size="small"
              @click.stop="confirmDeleteRepo(repo.name)"
            >
              删除
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 代码浏览视图 -->
    <div v-else class="code-viewer-container">
      <div class="code-viewer-header">
        <div class="breadcrumb">
          <a-button type="text" @click="selectedRepo = null">
            <ArrowLeft size="16" />
            返回仓库列表
          </a-button>
          <span class="separator">/</span>
          <span class="repo-name">{{ selectedRepo }}</span>
          <span v-if="currentPath" class="separator">/</span>
          <span v-if="currentPath" class="path">{{ currentPath }}</span>
        </div>
      </div>

      <div class="code-viewer-content" :class="{ 'with-chat-panel': showChatPanel }">
        <!-- 文件树侧边栏 -->
        <div class="file-tree-sidebar">
          <div class="file-tree-header">
            <h4>文件树</h4>
            <a-button type="text" size="small" @click="loadTree()">
              <RefreshCw size="14" />
            </a-button>
          </div>
          <div class="file-tree" v-if="fileTree && fileTree.tree">
            <FileTreeItem
              v-for="item in fileTree.tree"
              :key="item.path"
              :item="item"
              :current-path="currentPath"
              :repo-name="selectedRepo"
              @select="handleFileSelect"
            />
          </div>
          <div v-else class="loading-tree">
            <a-spin />
          </div>
        </div>

        <!-- 代码内容区域 -->
        <div class="code-content-area">
          <div v-if="loadingFile" class="loading-file">
            <a-spin />
            <p>正在加载文件...</p>
          </div>
          <div v-else-if="fileContent" class="file-viewer">
            <div class="file-header">
              <span class="file-name">{{ fileContent.name }}</span>
              <span class="file-size" v-if="fileContent.size">
                {{ formatFileSize(fileContent.size) }}
              </span>
            </div>
            <div class="file-content-wrapper">
              <!-- Markdown 文件渲染 -->
              <div v-if="!fileContent.is_binary && isMarkdownFile" class="markdown-viewer" ref="markdownViewerRef">
                <MdPreview
                  :modelValue="processedMarkdownContent"
                  theme="light"
                  previewTheme="github"
                  codeTheme="atom"
                />
              </div>
              <!-- 其他文本文件代码显示 -->
              <div v-else-if="!fileContent.is_binary" class="code-block-wrapper" @mouseup="handleCodeSelection" @click.self="clearSelection">
                <pre class="code-block"><code ref="codeRef" :class="codeLanguage">{{ fileContent.content }}</code></pre>
                <!-- 代码选择浮动按钮 -->
                <div 
                  v-if="selectedCode" 
                  class="code-selection-popup"
                  :style="{ top: selectionPopupPosition.top + 'px', left: selectionPopupPosition.left + 'px' }"
                  @click.stop
                >
                  <a-button type="primary" size="small" @click="askAboutCode">
                    <MessageSquare size="14" style="margin-right: 4px;" />
                    询问代码
                  </a-button>
                </div>
              </div>
              <!-- 二进制文件提示 -->
              <div v-else class="binary-file">
                <p>这是一个二进制文件，无法直接查看</p>
                <p>文件大小: {{ formatFileSize(fileContent.size) }}</p>
              </div>
            </div>
          </div>
          <div v-else class="empty-file-view">
            <p>选择一个文件查看内容</p>
          </div>
        </div>
        
        <!-- 右侧聊天面板 -->
        <div v-if="showChatPanel" class="chat-panel">
          <div class="chat-panel-header">
            <h4>代码问答</h4>
            <a-button type="text" size="small" @click="closeChatPanel">
              <X size="16" />
            </a-button>
          </div>
          <div class="chat-panel-content">
            <!-- 代码预览区域 - 只在代码上下文还没有传递给 AgentChatComponent 时显示 -->
            <!-- 一旦代码上下文传递给 AgentChatComponent，就会在输入框上方显示，这里就不需要显示了 -->
            <div v-if="selectedCodeInfo && !codeContextPassedToChat" class="code-preview-section">
              <div class="code-preview-header">
                <div class="code-preview-info">
                  <span class="code-file-name">
                    <FileText size="14" />
                    {{ selectedCodeInfo.fileName || selectedCodeInfo.filePath }}
                  </span>
                  <span v-if="selectedCodeInfo.repoName" class="code-repo-name">
                    {{ selectedCodeInfo.repoName }}
                  </span>
                </div>
                <a-button type="text" size="small" @click="clearCodePreview">
                  <X size="14" />
                </a-button>
              </div>
              <div class="code-preview-content">
                <pre><code ref="codePreviewRef" :class="`language-${selectedCodeInfo.language || 'text'}`">{{ selectedCodeInfo.selectedCode }}</code></pre>
              </div>
            </div>
            <AgentChatComponent
              ref="chatComponentRef"
              :agent-id="props.agentId"
              :single-mode="true"
              class="embedded-chat"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useUserStore } from '@/stores/user';
import { message, Modal } from 'ant-design-vue';
import { FolderGit2, ArrowLeft, RefreshCw, MessageSquare, X, FileText } from 'lucide-vue-next';
import { MdPreview } from 'md-editor-v3';
import 'md-editor-v3/lib/preview.css';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.min.css';
import { codehubApi } from '@/apis/codehub_api';
import HeaderComponent from '@/components/HeaderComponent.vue';
import FileTreeItem from '@/components/FileTreeItem.vue';
import AgentChatComponent from '@/components/AgentChatComponent.vue';

// Props
const props = defineProps({
  showBackButton: {
    type: Boolean,
    default: false
  },
  agentId: {
    type: String,
    default: ''
  }
});

// Emits
const emit = defineEmits(['back', 'ask-code']);

const loading = ref(false);
const selectedCode = ref('');
const selectionPopupPosition = ref({ top: 0, left: 0 });
const showChatPanel = ref(false);
const chatComponentRef = ref(null);
const selectedCodeInfo = ref(null); // 存储选中的代码信息
const codePreviewRef = ref(null);
const repositories = ref([]);
const selectedRepo = ref(null);
const currentPath = ref('');
const fileTree = ref(null);
const fileContent = ref(null);
const loadingFile = ref(false);
const markdownViewerRef = ref(null);
const codeRef = ref(null);
let imageObserver = null;

// 判断是否是 Markdown 文件
const isMarkdownFile = computed(() => {
  if (!fileContent.value) return false;
  const fileName = fileContent.value.name.toLowerCase();
  return fileName.endsWith('.md') || fileName.endsWith('.markdown');
});

// 处理 Markdown 内容中的图片路径
const processedMarkdownContent = computed(() => {
  if (!fileContent.value || !isMarkdownFile.value || !selectedRepo.value) {
    return fileContent.value?.content || '';
  }
  
  const content = fileContent.value.content;
  // 获取当前文件所在目录（去掉文件名）
  const currentDir = currentPath.value ? currentPath.value.split('/').slice(0, -1).join('/') : '';
  
  // 解析相对路径为绝对路径（相对于仓库根目录）
  const resolvePath = (relativePath) => {
    // 如果是完整的 URL，保持不变
    if (relativePath.startsWith('http://') || relativePath.startsWith('https://') || relativePath.startsWith('//')) {
      return null; // 返回 null 表示不需要转换
    }
    
    // 处理相对路径
    let assetPath = relativePath;
    
    if (relativePath.startsWith('./')) {
      // ./image.png -> 相对于当前目录
      assetPath = currentDir ? `${currentDir}/${relativePath.slice(2)}` : relativePath.slice(2);
    } else if (relativePath.startsWith('../')) {
      // 处理 ../ 相对路径
      const parts = currentDir ? currentDir.split('/').filter(p => p) : [];
      let relative = relativePath;
      while (relative.startsWith('../')) {
        if (parts.length > 0) {
          parts.pop();
          relative = relative.slice(3);
        } else {
          // 已经到根目录了，不能再往上
          relative = relative.slice(3);
          break;
        }
      }
      assetPath = parts.length > 0 ? `${parts.join('/')}/${relative}` : relative;
    } else if (relativePath.startsWith('/')) {
      // 绝对路径（从仓库根目录开始）
      assetPath = relativePath.slice(1);
    } else {
      // 相对路径，相对于当前目录
      assetPath = currentDir ? `${currentDir}/${relativePath}` : relativePath;
    }
    
    // 清理路径中的多余斜杠和 ./
    assetPath = assetPath.replace(/\/+/g, '/').replace(/^\.\//, '').replace(/\/\.\//g, '/');
    
    return assetPath;
  };
  
  // 替换 Markdown 图片语法 ![alt](path)
  let processed = content.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, imgPath) => {
    const resolvedPath = resolvePath(imgPath.trim());
    if (resolvedPath === null) {
      return match; // 完整 URL，保持不变
    }
    const apiUrl = `/api/codehub/repositories/${encodeURIComponent(selectedRepo.value)}/assets/${encodeURIComponent(resolvedPath)}`;
    return `![${alt}](${apiUrl})`;
  });
  
  // 替换 HTML img 标签 <img src="path" />
  processed = processed.replace(/<img([^>]+)src=["']([^"']+)["']([^>]*)>/gi, (match, before, imgPath, after) => {
    const resolvedPath = resolvePath(imgPath.trim());
    if (resolvedPath === null) {
      return match; // 完整 URL，保持不变
    }
    const apiUrl = `/api/codehub/repositories/${encodeURIComponent(selectedRepo.value)}/assets/${encodeURIComponent(resolvedPath)}`;
    return `<img${before}src="${apiUrl}"${after}>`;
  });
  
  return processed;
});

// 计算代码语言类型
const codeLanguage = computed(() => {
  if (!fileContent.value) return '';
  const fileName = fileContent.value.name;
  const ext = fileName.split('.').pop()?.toLowerCase();
  
  const languageMap = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp',
    'c': 'c',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'php': 'php',
    'rb': 'ruby',
    'swift': 'swift',
    'kt': 'kotlin',
    'vue': 'vue',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sh': 'bash',
    'bash': 'bash',
    'sql': 'sql',
    'dockerfile': 'dockerfile',
    'makefile': 'makefile',
  };
  
  return `language-${languageMap[ext] || 'text'}`;
});

// 加载仓库列表
const loadRepositories = async () => {
  loading.value = true;
  try {
    const response = await codehubApi.getRepositories();
    repositories.value = response.repositories || [];
  } catch (error) {
    console.error('加载仓库列表失败:', error);
    message.error('加载仓库列表失败');
  } finally {
    loading.value = false;
  }
};

// 选择仓库
const selectRepository = async (repoName) => {
  selectedRepo.value = repoName;
  currentPath.value = '';
  fileContent.value = null;
  await loadTree();
};

// 加载文件树
const loadTree = async (path = '') => {
  if (!selectedRepo.value) return;
  
  try {
    const response = await codehubApi.getRepositoryTree(selectedRepo.value, path);
    if (response.type === 'file') {
      // 如果返回的是文件，直接加载文件内容
      await handleFileSelect(path);
    } else {
      fileTree.value = response;
    }
  } catch (error) {
    console.error('加载文件树失败:', error);
    message.error('加载文件树失败');
  }
};

// 处理文件选择
const handleFileSelect = async (filePath) => {
  if (!selectedRepo.value) return;
  
  currentPath.value = filePath;
  loadingFile.value = true;
  fileContent.value = null;
  
  try {
    const response = await codehubApi.getFileContent(selectedRepo.value, filePath);
    fileContent.value = response;
    
    // 等待 DOM 更新后高亮代码
    await nextTick();
    highlightCode();
  } catch (error) {
    console.error('加载文件内容失败:', error);
    message.error('加载文件内容失败');
  } finally {
    loadingFile.value = false;
  }
};

// 高亮代码
const highlightCode = () => {
  if (!codeRef.value || !fileContent.value || fileContent.value.is_binary || isMarkdownFile.value) {
    return;
  }
  
  try {
    const codeElement = codeRef.value;
    const language = getLanguageFromFileName(fileContent.value.name);
    
    // 确保 code 元素有 hljs 类
    if (!codeElement.classList.contains('hljs')) {
      codeElement.classList.add('hljs');
    }
    
    if (language && hljs.getLanguage(language)) {
      // 使用 highlight.js 高亮代码
      const result = hljs.highlight(fileContent.value.content, { language });
      codeElement.innerHTML = result.value;
      codeElement.className = `hljs language-${language}`;
    } else {
      // 如果没有匹配的语言，尝试自动检测
      const result = hljs.highlightAuto(fileContent.value.content);
      codeElement.innerHTML = result.value;
      if (result.language) {
        codeElement.className = `hljs language-${result.language}`;
      }
    }
  } catch (error) {
    console.error('代码高亮失败:', error);
    // 如果高亮失败，显示原始内容
    if (codeRef.value) {
      codeRef.value.textContent = fileContent.value.content;
      codeRef.value.classList.remove('hljs');
    }
  }
};

// 从文件名获取语言类型
const getLanguageFromFileName = (fileName) => {
  const ext = fileName.split('.').pop()?.toLowerCase();
  
  const languageMap = {
    'js': 'javascript',
    'jsx': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    'py': 'python',
    'java': 'java',
    'cpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'c': 'c',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'php': 'php',
    'rb': 'ruby',
    'swift': 'swift',
    'kt': 'kotlin',
    'vue': 'vue',
    'html': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'scss',
    'less': 'less',
    'json': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'md': 'markdown',
    'sh': 'bash',
    'bash': 'bash',
    'zsh': 'bash',
    'sql': 'sql',
    'dockerfile': 'dockerfile',
    'makefile': 'makefile',
    'cmake': 'cmake',
    'r': 'r',
    'matlab': 'matlab',
    'scala': 'scala',
    'clj': 'clojure',
    'hs': 'haskell',
    'erl': 'erlang',
    'ex': 'elixir',
    'lua': 'lua',
    'pl': 'perl',
    'vim': 'vim',
    'diff': 'diff',
    'patch': 'diff',
  };
  
  return languageMap[ext] || null;
};

// 确认删除仓库
const confirmDeleteRepo = (repoName) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除仓库 "${repoName}" 吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      try {
        await codehubApi.deleteRepository(repoName);
        message.success('仓库已删除');
        await loadRepositories();
        if (selectedRepo.value === repoName) {
          selectedRepo.value = null;
          fileTree.value = null;
          fileContent.value = null;
        }
      } catch (error) {
        console.error('删除仓库失败:', error);
        message.error('删除仓库失败');
      }
    },
  });
};

// 处理单个图片加载
const processImage = async (img) => {
  // 如果已经处理过，跳过
  if (img.dataset.processed === 'true') {
    return;
  }
  
  const originalSrc = img.getAttribute('src') || img.src;
  if (!originalSrc) return;
  
  // 如果已经是 blob URL 或 data URL，跳过
  if (originalSrc.startsWith('blob:') || originalSrc.startsWith('data:')) {
    return;
  }
  
  // 如果是完整的 URL，保持不变
  if (originalSrc.startsWith('http://') || originalSrc.startsWith('https://')) {
    return;
  }
  
  // 如果是 API 路径，通过 fetch 获取
  if (originalSrc.startsWith('/api/codehub/repositories/')) {
    // 标记已处理，避免重复处理
    img.dataset.processed = 'true';
    img.dataset.originalSrc = originalSrc; // 保存原始src
    
    // 阻止浏览器自动加载（移除src，使用data-src存储）
    img.removeAttribute('src');
    img.setAttribute('data-src', originalSrc);
    img.style.opacity = '0';
    
    try {
      const userStore = useUserStore();
      const response = await fetch(originalSrc, {
        headers: {
          ...userStore.getAuthHeaders(),
        },
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        img.src = blobUrl;
        img.style.opacity = '1';
      } else {
        console.error('加载图片失败:', response.status, originalSrc);
        // 设置占位符
        img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
        img.style.opacity = '1';
      }
    } catch (error) {
      console.error('加载图片异常:', error, originalSrc);
      // 设置占位符
      img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
      img.style.opacity = '1';
    }
  }
};

// 处理 Markdown HTML 变化，拦截图片加载
const handleMarkdownHtmlChanged = async () => {
  if (!markdownViewerRef.value) return;
  
  // 先断开旧的观察者
  if (imageObserver) {
    imageObserver.disconnect();
  }
  
  // 等待 DOM 更新
  await nextTick();
  
  // 先查找并处理现有图片（立即处理，不等待）
  const processExistingImages = () => {
    const images = markdownViewerRef.value?.querySelectorAll('img');
    if (images) {
      images.forEach((img) => {
        // 立即处理，不等待
        processImage(img);
      });
    }
  };
  
  // 立即处理一次
  processExistingImages();
  
  // 设置 MutationObserver 监听DOM变化
  imageObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      // 处理新增的节点
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1) { // Element node
          // 检查是否是图片节点
          if (node.tagName === 'IMG') {
            processImage(node);
          }
          // 检查子节点中的图片
          const images = node.querySelectorAll?.('img');
          if (images) {
            images.forEach((img) => processImage(img));
          }
        }
      });
      
      // 处理src属性变化
      if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
        const target = mutation.target;
        if (target.tagName === 'IMG') {
          processImage(target);
        }
      }
    });
  });
  
  // 开始观察
  imageObserver.observe(markdownViewerRef.value, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['src'],
  });
  
  // 延迟处理，确保所有图片都已渲染
  setTimeout(() => {
    processExistingImages();
  }, 100);
  
  setTimeout(() => {
    processExistingImages();
  }, 300);
};

// 处理返回
const handleBack = () => {
  emit('back');
};

// 清空选择
const clearSelection = () => {
  selectedCode.value = '';
  window.getSelection()?.removeAllRanges();
};

// 处理代码选择
const handleCodeSelection = (event) => {
  // 延迟处理，确保选择完成
  setTimeout(() => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) {
      selectedCode.value = '';
      return;
    }
    
    const selectedText = selection.toString().trim();
    if (!selectedText) {
      selectedCode.value = '';
      return;
    }
    
    // 检查选中的内容是否在代码块内
    const range = selection.getRangeAt(0);
    const codeElement = codeRef.value;
    if (!codeElement) {
      selectedCode.value = '';
      return;
    }
    
    // 检查选中内容是否在代码元素内（包括高亮后的子元素）
    let node = range.commonAncestorContainer;
    let isInCodeBlock = false;
    
    // 向上遍历查找是否在代码块内
    while (node) {
      if (node === codeElement || codeElement.contains(node)) {
        isInCodeBlock = true;
        break;
      }
      node = node.parentNode;
    }
    
    if (!isInCodeBlock) {
      selectedCode.value = '';
      return;
    }
    
    selectedCode.value = selectedText;
    
    // 计算浮动按钮位置
    try {
      const rect = range.getBoundingClientRect();
      const wrapper = event?.currentTarget;
      if (!wrapper) {
        return;
      }
      const wrapperRect = wrapper.getBoundingClientRect();
      
      selectionPopupPosition.value = {
        top: rect.top - wrapperRect.top + rect.height + 8,
        left: Math.min(rect.left - wrapperRect.left + rect.width / 2 - 60, wrapperRect.width - 140)
      };
    } catch (error) {
      console.warn('计算浮动按钮位置失败:', error);
      // 使用默认位置
      selectionPopupPosition.value = {
        top: 50,
        left: 50
      };
    }
  }, 10);
};

// 询问代码
const askAboutCode = async () => {
  if (!selectedCode.value) return;
  
  // 检查 agentId
  if (!props.agentId || props.agentId.trim() === '') {
    message.warning('无法提问：缺少智能体ID，请返回聊天界面选择智能体');
    return;
  }
  
  // 打开聊天面板
  showChatPanel.value = true;
  
  // 等待面板渲染
  await nextTick();
  
  // 获取文件信息
  const fileInfo = {
    fileName: fileContent.value?.name || '',
    filePath: currentPath.value || '',
    repoName: selectedRepo.value || '',
    selectedCode: selectedCode.value,
    language: getLanguageFromFileName(fileContent.value?.name || '')
  };
  
  // 保存代码信息到预览区域
  selectedCodeInfo.value = fileInfo;
  
  // 设置输入框初始内容（用户可以继续编辑）
  const initialQuestion = '请帮我分析这段代码：';
  
  // 等待组件加载并设置输入框内容
  // selectedCodeInfo 的设置会触发 watch，自动将代码上下文传递给 AgentChatComponent
  await nextTick();
  setTimeout(() => {
    if (chatComponentRef.value) {
      // 设置输入框内容
      chatComponentRef.value.setUserInput(initialQuestion);
      
      // 聚焦输入框，方便用户继续编辑
      setTimeout(() => {
        // 尝试聚焦输入框 - 通过多层查找
        const chatContainer = chatComponentRef.value?.$el;
        if (chatContainer) {
          const inputElement = chatContainer.querySelector('textarea.user-input');
          if (inputElement) {
            inputElement.focus();
            // 将光标移动到末尾
            const length = inputElement.value.length;
            inputElement.setSelectionRange(length, length);
            // 滚动到底部
            inputElement.scrollTop = inputElement.scrollHeight;
          }
        }
      }, 150);
    }
  }, 300);
  
  // 清空选择
  clearSelection();
};

// 清空代码预览
const clearCodePreview = () => {
  selectedCodeInfo.value = null;
  codeContextPassedToChat.value = false;
};

// 监听代码预览变化，应用高亮
watch(selectedCodeInfo, async (newInfo) => {
  if (newInfo && codePreviewRef.value) {
    await nextTick();
    try {
      const codeElement = codePreviewRef.value;
      const language = newInfo.language;
      
      if (language && hljs.getLanguage(language)) {
        const result = hljs.highlight(newInfo.selectedCode, { language });
        codeElement.innerHTML = result.value;
        codeElement.className = `hljs language-${language}`;
      } else {
        const result = hljs.highlightAuto(newInfo.selectedCode);
        codeElement.innerHTML = result.value;
        if (result.language) {
          codeElement.className = `hljs language-${result.language}`;
        }
      }
    } catch (error) {
      console.error('代码高亮失败:', error);
    }
  }
}, { flush: 'post' });

// 标志位：代码上下文是否已经传递给 AgentChatComponent
const codeContextPassedToChat = ref(false);

// 当选中的代码信息变化时，同步到 AgentChatComponent
watch(selectedCodeInfo, (newCodeInfo) => {
  if (chatComponentRef.value) {
    if (newCodeInfo) {
      // 将代码上下文传递给 AgentChatComponent
      chatComponentRef.value.setCodeContext(newCodeInfo);
      codeContextPassedToChat.value = true; // 标记已传递
    } else {
      // 清空代码上下文
      chatComponentRef.value.clearCodeContext();
      codeContextPassedToChat.value = false; // 重置标志
    }
  } else if (!newCodeInfo) {
    // 如果组件还没加载但代码信息被清空，也要重置标志
    codeContextPassedToChat.value = false;
  }
});

// 监听组件引用，当组件加载后，如果已有代码信息，立即同步
watch(chatComponentRef, (newRef) => {
  if (newRef && selectedCodeInfo.value) {
    // 组件已加载且有代码信息，立即同步
    newRef.setCodeContext(selectedCodeInfo.value);
    codeContextPassedToChat.value = true;
  }
}, { immediate: true });

// 关闭聊天面板
const closeChatPanel = () => {
  showChatPanel.value = false;
  // 清空代码预览（会自动触发 watch，同步清空 AgentChatComponent 中的代码上下文）
  selectedCodeInfo.value = null;
  codeContextPassedToChat.value = false;
};

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};

// 监听 Markdown 内容变化，处理图片加载
watch([processedMarkdownContent, markdownViewerRef], async () => {
  if (isMarkdownFile.value && markdownViewerRef.value) {
    // 使用 setTimeout 确保 DOM 已完全渲染
    setTimeout(async () => {
      await handleMarkdownHtmlChanged();
    }, 100);
  }
}, { flush: 'post', immediate: true });

// 监听文件内容变化，重新高亮代码
watch([fileContent, codeRef], () => {
  if (fileContent.value && !fileContent.value.is_binary && !isMarkdownFile.value) {
    nextTick(() => {
      highlightCode();
    });
  }
}, { flush: 'post' });

// 监听路径变化，重新加载文件树
watch([selectedRepo, currentPath], () => {
  if (selectedRepo.value && !fileContent.value) {
    loadTree(currentPath.value);
  }
});

onMounted(() => {
  loadRepositories();
});

onUnmounted(() => {
  // 清理 MutationObserver
  if (imageObserver) {
    imageObserver.disconnect();
    imageObserver = null;
  }
});
</script>

<style scoped lang="less">
.codehub-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  
  // 移除左侧 padding，消除与侧边栏的间隙
  &.layout-container {
    padding-left: 0;
    padding-right: 0;
  }
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  gap: 20px;
}

.repositories-list {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
  
  .empty-icon {
    color: var(--gray-400);
    margin-bottom: 24px;
  }
  
  h3 {
    margin: 0 0 12px;
    font-size: 20px;
    color: var(--gray-800);
  }
  
  p {
    margin: 0;
    color: var(--gray-600);
  }
}

.repositories-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.repo-card {
  background: white;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    border-color: var(--main-color);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
  
  .repo-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
    
    .repo-icon {
      color: var(--main-color);
    }
    
    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }
  }
  
  .repo-info {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    
    .repo-url {
      font-size: 12px;
      color: var(--gray-600);
      word-break: break-all;
    }
  }
  
  .repo-actions {
    display: flex;
    justify-content: flex-end;
  }
}

.code-viewer-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.code-viewer-header {
  padding: 12px 24px;
  background: var(--bg-sider);
  border-bottom: 1px solid var(--gray-200);
  
  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    
    .separator {
      color: var(--gray-400);
    }
    
    .repo-name {
      font-weight: 500;
      color: var(--gray-800);
    }
    
    .path {
      color: var(--gray-600);
    }
  }
}

.code-viewer-content {
  flex: 1;
  display: flex;
  overflow: hidden;
  
  &.with-chat-panel {
    .code-content-area {
      flex: 1;
      min-width: 0; // 允许缩小
    }
  }
}

.file-tree-sidebar {
  width: 300px;
  border-right: 1px solid var(--gray-200);
  display: flex;
  flex-direction: column;
  background: var(--bg-sider);
  overflow: hidden;
  
  .file-tree-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--gray-200);
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    h4 {
      margin: 0;
      font-size: 14px;
      font-weight: 500;
    }
  }
  
  .file-tree {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }
  
  .loading-tree {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.code-content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: white;
}

.loading-file {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.file-viewer {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-header {
  padding: 12px 24px;
  border-bottom: 1px solid var(--gray-200);
  display: flex;
  align-items: center;
  gap: 12px;
  
  .file-name {
    font-weight: 500;
    color: var(--gray-800);
  }
  
  .file-size {
    font-size: 12px;
    color: var(--gray-500);
  }
}

.file-content-wrapper {
  flex: 1;
  overflow: auto;
  
  .markdown-viewer {
    padding: 24px;
    background: white;
    min-height: 100%;
    
    :deep(.md-editor) {
      border: none;
      box-shadow: none;
    }
    
    :deep(.md-editor-preview) {
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: var(--gray-800);
    }
    
    :deep(.md-editor-preview-wrapper) {
      padding: 0;
    }
    
    :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
      margin-top: 24px;
      margin-bottom: 16px;
      font-weight: 600;
      line-height: 1.25;
    }
    
    :deep(h1) {
      font-size: 2em;
      border-bottom: 1px solid var(--gray-200);
      padding-bottom: 0.3em;
    }
    
    :deep(h2) {
      font-size: 1.5em;
      border-bottom: 1px solid var(--gray-200);
      padding-bottom: 0.3em;
    }
    
    :deep(p) {
      margin-bottom: 16px;
    }
    
    :deep(code) {
      padding: 0.2em 0.4em;
      margin: 0;
      font-size: 85%;
      background-color: rgba(27, 31, 35, 0.05);
      border-radius: 3px;
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    }
    
    :deep(pre) {
      padding: 16px;
      overflow: auto;
      font-size: 85%;
      line-height: 1.45;
      background-color: #f6f8fa;
      border-radius: 6px;
      margin-bottom: 16px;
      
      code {
        display: inline;
        padding: 0;
        margin: 0;
        overflow: visible;
        line-height: inherit;
        word-wrap: normal;
        background-color: transparent;
        border: 0;
      }
    }
    
    :deep(blockquote) {
      padding: 0 1em;
      color: var(--gray-600);
      border-left: 0.25em solid #dfe2e5;
      margin-bottom: 16px;
    }
    
    :deep(table) {
      border-collapse: collapse;
      margin-bottom: 16px;
      width: 100%;
      
      th, td {
        padding: 6px 13px;
        border: 1px solid #dfe2e5;
      }
      
      th {
        font-weight: 600;
        background-color: #f6f8fa;
      }
    }
    
    :deep(ul), :deep(ol) {
      margin-bottom: 16px;
      padding-left: 2em;
    }
    
    :deep(li) {
      margin-bottom: 0.25em;
    }
    
    :deep(img) {
      max-width: 100%;
      box-sizing: content-box;
      background-color: white;
      border-radius: 4px;
      display: block;
      margin: 16px 0;
    }
    
    // 确保图片加载失败时有提示
    :deep(img[src]) {
      min-height: 50px;
      background-color: #f5f5f5;
    }
    
    :deep(a) {
      color: var(--main-color);
      text-decoration: none;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
  
  .code-block-wrapper {
    position: relative;
  }
  
  .code-block {
    margin: 0;
    padding: 24px;
    background: #f8f9fa;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 14px;
    line-height: 1.6;
    overflow-x: auto;
    
    code {
      display: block;
      white-space: pre;
      background: transparent;
      padding: 0;
      margin: 0;
      font-size: inherit;
      line-height: inherit;
      color: inherit;
      
      // highlight.js 样式覆盖
      &.hljs {
        background: transparent;
        padding: 0;
        display: block;
        overflow-x: auto;
        color: inherit;
      }
    }
  }
  
  .code-selection-popup {
    position: absolute;
    z-index: 1000;
    background: white;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    padding: 4px;
    animation: fadeIn 0.2s ease-in-out;
    pointer-events: auto;
    
    @keyframes fadeIn {
      from {
        opacity: 0;
        transform: translateY(-4px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    // 确保按钮样式正确
    :deep(.ant-btn) {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }
  
  .binary-file {
    padding: 60px 24px;
    text-align: center;
    color: var(--gray-600);
  }
}

.empty-file-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-500);
}

// 聊天面板样式
.chat-panel {
  width: 500px;
  border-left: 1px solid var(--gray-200);
  display: flex;
  flex-direction: column;
  background: white;
  animation: slideInRight 0.3s ease-out;
  flex-shrink: 0;
  
  @keyframes slideInRight {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  .chat-panel-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--gray-200);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-sider);
    flex-shrink: 0;
    
    h4 {
      margin: 0;
      font-size: 14px;
      font-weight: 500;
      color: var(--gray-800);
    }
  }
  
  .chat-panel-content {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 0;
    
    :deep(.chat-container) {
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    
    // 隐藏侧边栏，因为是在面板中嵌入
    :deep(.embedded-chat) {
      .chat-sidebar,
      .sidebar-backdrop {
        display: none !important;
      }
      
      .chat {
        width: 100% !important;
        margin-left: 0 !important;
      }
    }
  }
  
  // 代码预览区域样式
  .code-preview-section {
    border-bottom: 1px solid var(--gray-200);
    background: var(--bg-sider);
    flex-shrink: 0;
    animation: slideDown 0.2s ease-out;
    
    @keyframes slideDown {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    
    .code-preview-header {
      padding: 8px 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid var(--gray-200);
      
      .code-preview-info {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;
        min-width: 0;
        
        .code-file-name {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          font-weight: 500;
          color: var(--gray-800);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .code-repo-name {
          font-size: 11px;
          color: var(--gray-500);
          padding: 2px 6px;
          background: var(--gray-100);
          border-radius: 4px;
          flex-shrink: 0;
        }
      }
    }
    
    .code-preview-content {
      padding: 12px;
      max-height: 200px;
      overflow-y: auto;
      background: #f8f9fa;
      
      pre {
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 12px;
        line-height: 1.5;
        
        code {
          display: block;
          white-space: pre;
          padding: 0;
          margin: 0;
          background: transparent;
          color: inherit;
          
          // highlight.js 样式
          &.hljs {
            background: transparent;
            padding: 0;
            display: block;
            overflow-x: auto;
          }
        }
      }
    }
  }
}

// 响应式：小屏幕时聊天面板全屏
@media (max-width: 768px) {
  .chat-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    z-index: 1000;
    box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  }
  
  .code-viewer-content.with-chat-panel {
    .code-content-area {
      opacity: 0.3;
      pointer-events: none;
    }
  }
}
</style>

