<template>
  <div class="message-container" :class="message.type">
    <!-- 图片内容 - 显示在消息框外部 -->
    <div v-if="message.type === 'human' && messageImages && messageImages.length > 0" class="message-images">
      <div class="images-grid" :class="`images-count-${Math.min(messageImages.length, 3)}`">
        <div 
          v-for="(img, index) in messageImages" 
          :key="index"
          class="message-image-wrapper"
          @click="previewImage(img, index)"
        >
          <img :src="img.url" :alt="img.name || '图片'" class="message-image" />
        </div>
      </div>
    </div>
    
    <!-- 代码上下文 - 显示在消息框外部 -->
    <div v-if="message.type === 'human' && messageCodeContext" class="message-code-context">
      <div class="code-context-header">
        <div class="code-context-info">
          <FileText :size="16" />
          <span class="code-file-name">{{ messageCodeContext.fileName || '选中的代码' }}</span>
          <span v-if="messageCodeContext.repoName" class="code-repo-name">{{ messageCodeContext.repoName }}</span>
        </div>
      </div>
      <div class="code-context-content">
        <pre><code ref="messageCodeRef" class="hljs">{{ messageCodeContext.selectedCode }}</code></pre>
      </div>
    </div>
    
    <!-- 文件内容 - 显示在消息框外部 -->
    <div v-if="message.type === 'human' && messageFiles && messageFiles.length > 0" class="message-files">
      <div 
        v-for="(file, index) in messageFiles" 
        :key="index"
        class="message-file-item"
      >
        <FileOutlined class="file-icon" />
        <div class="file-info">
          <div class="file-name" :title="file.name">{{ file.name }}</div>
          <div class="file-size">{{ formatFileSize(file.size) }}</div>
        </div>
        <a-button
          v-if="file.extractedText"
          type="link"
          size="small"
          @click="previewFileContent(file)"
          class="preview-btn"
        >
          <EyeOutlined /> 预览
        </a-button>
        <a-button
          v-if="file.hasVisualization"
          type="link"
          size="small"
          @click="showFileVisualization(file)"
          class="viz-btn"
        >
          <FileSearchOutlined /> 可视化
        </a-button>
      </div>
    </div>
    
    <div class="message-box" :class="[message.type, customClasses]">
      <!-- 用户消息 -->
      <div v-if="message.type === 'human'" class="human-message">
        <!-- 文本内容 -->
        <p v-if="messageText" class="message-text">{{ messageText }}</p>
      </div>

    <!-- 助手消息 -->
    <div v-else-if="message.type === 'ai'" class="assistant-message">
      <div v-if="parsedData.reasoning_content" class="reasoning-box">
        <a-collapse v-model:activeKey="reasoningActiveKey" :bordered="false">
          <template #expandIcon="{ isActive }">
            <caret-right-outlined :rotate="isActive ? 90 : 0" />
          </template>
          <a-collapse-panel key="show" :header="message.status=='reasoning' ? '正在思考...' : '推理过程'" class="reasoning-header">
            <p class="reasoning-content">{{ parsedData.reasoning_content }}</p>
          </a-collapse-panel>
        </a-collapse>
      </div>

      <!-- 消息内容 -->
      <MdPreview v-if="parsedData.content" ref="editorRef"
        editorId="preview-only"
        previewTheme="github"
        :showCodeRowNumber="false"
        :modelValue="parsedData.content"
        :key="message.id"
        class="message-md"/>

      <div v-else-if="parsedData.reasoning_content"  class="empty-block"></div>

      <div v-if="message.tool_calls && Object.keys(message.tool_calls).length > 0" class="tool-calls-container">
        <div v-for="(toolCall, index) in message.tool_calls || {}" :key="index" class="tool-call-container">
          <div v-if="toolCall" class="tool-call-display" :class="{ 'is-collapsed': !expandedToolCalls.has(toolCall.id) }">
            <div class="tool-header" @click="toggleToolCall(toolCall.id)">
              <span v-if="!toolCall.tool_call_result">
                <span><Loader size="16" class="tool-loader rotate tool-loading" /></span> &nbsp;
                <span>正在调用工具: </span>
                <span class="tool-name">{{ getToolNameByToolCall(toolCall) }}</span>
              </span>
              <span v-else>
                <span><CircleCheckBig size="16" class="tool-loader tool-success" /></span> &nbsp; 工具 <span class="tool-name">{{ getToolNameByToolCall(toolCall) }}</span> 执行完成
              </span>
            </div>
            <div class="tool-content" v-show="expandedToolCalls.has(toolCall.id)">
              <div class="tool-params" v-if="toolCall.args || toolCall.function.arguments">
                <div class="tool-params-content">
                  <strong>参数:</strong> {{ toolCall.args || toolCall.function.arguments }}
                </div>
              </div>
              <div class="tool-result" v-if="toolCall.tool_call_result && toolCall.tool_call_result.content">
                <div class="tool-result-content" :data-tool-call-id="toolCall.id">
                  <ToolResultRenderer
                    :tool-name="toolCall.name || toolCall.function.name"
                    :result-content="toolCall.tool_call_result.content"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="message.isStoppedByUser" class="retry-hint">
        你停止生成了本次回答
        <span class="retry-link" @click="emit('retryStoppedMessage', message.id)">重新编辑问题</span>
      </div>


      <div v-if="(message.role=='received' || message.role=='assistant') && message.status=='finished' && showRefs">
        <RefsComponent :message="message" :show-refs="showRefs" :is-latest-message="isLatestMessage" @retry="emit('retry')" @openRefs="emit('openRefs', $event)" />
      </div>
      <!-- 错误消息 -->
    </div>

    <div v-if="infoStore.debugMode" class="status-info">{{ message }}</div>

    <!-- 自定义内容 -->
    <slot></slot>
    </div>

    <!-- 文件预览模态框 -->
    <a-modal
      v-model:open="filePreviewVisible"
      :title="filePreviewTitle"
      :footer="null"
      :width="filePreviewModalWidth"
      :centered="true"
      class="file-preview-modal"
      @cancel="closeFilePreview"
    >
      <div class="file-preview-modal-content">
        <MdPreview
          v-if="filePreviewVisible && filePreviewContent"
          editorId="file-preview-editor"
          :modelValue="filePreviewContent"
          previewTheme="github"
          class="markdown-preview"
        />
        <div v-else class="empty-content">
          <FileOutlined />
          <span>暂无内容</span>
        </div>
      </div>
      <template #footer>
        <div class="modal-footer">
          <a-button type="primary" @click="closeFilePreview">关闭</a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue';
import { CaretRightOutlined, ThunderboltOutlined, LoadingOutlined, FileOutlined, EyeOutlined, FileSearchOutlined } from '@ant-design/icons-vue';
import { Image as AImage } from 'ant-design-vue';
import RefsComponent from '@/components/RefsComponent.vue'
import { Loader, CircleCheckBig, FileText } from 'lucide-vue-next';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';
import { ToolResultRenderer } from '@/components/ToolCallingResult'
import { useAgentStore } from '@/stores/agent'
import { useInfoStore } from '@/stores/info'
import { storeToRefs } from 'pinia'


import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/preview.css';

const props = defineProps({
  // 消息角色：'user'|'assistant'|'sent'|'received'
  message: {
    type: Object,
    required: true
  },
  // 是否正在处理中
  isProcessing: {
    type: Boolean,
    default: false
  },
  // 自定义类
  customClasses: {
    type: Object,
    default: () => ({})
  },
  // 是否显示推理过程
  showRefs: {
    type: [Array, Boolean],
    default: () => false
  },
  // 是否为最新消息
  isLatestMessage: {
    type: Boolean,
    default: false
  }
});

const editorRef = ref()

const emit = defineEmits(['retry', 'retryStoppedMessage', 'openRefs']);

// 推理面板展开状态
const reasoningActiveKey = ref(['hide']);
const expandedToolCalls = ref(new Set()); // 展开的工具调用集合

// 引入智能体 store
const agentStore = useAgentStore();
const infoStore = useInfoStore();
const { availableTools } = storeToRefs(agentStore);

// 解析消息文本内容
const messageText = computed(() => {
  if (!props.message || props.message.type !== 'human') return '';
  
  try {
    let textContent = '';
    
    // 获取原始文本内容
    if (Array.isArray(props.message.content)) {
      const textItem = props.message.content.find(item => item.type === 'text');
      textContent = textItem?.text || '';
    } else if (typeof props.message.content === 'string') {
      // 如果是历史消息且有图片，尝试从 extra_metadata 中获取原始文本
      const rawMessage = props.message.extra_metadata?.raw_message;
      if (rawMessage && Array.isArray(rawMessage.content)) {
        const textItem = rawMessage.content.find(item => item.type === 'text');
        textContent = textItem?.text || props.message.content;
      } else {
        textContent = props.message.content;
      }
    }
    
    // 如果有代码上下文，需要提取用户问题部分（移除文件信息和代码块）
    if (props.message.codeContext) {
      // 匹配模式：用户问题\n\n文件：xxx\n仓库：xxx\n\n```代码```
      // 或者：用户问题\n\n```代码```
      // 文件信息和仓库信息之间只有一个换行，文件信息后是 \n\n 然后是代码块
      const codeBlockPattern = /\n\n(?:文件：[^\n]+(?:\n仓库：[^\n]+)?\n\n)?```/;
      const match = textContent.match(codeBlockPattern);
      if (match) {
        // 提取代码块之前的用户问题
        const userQuestion = textContent.substring(0, match.index).trim();
        return userQuestion || textContent; // 如果提取失败，返回原内容
      }
      // 如果没有匹配到，可能是新消息格式（content 已经是纯文本）
      return textContent;
    }
    
    // 如果没有 codeContext 但文本中包含代码块，则只显示代码块之前的部分
    // 这是为了处理历史消息（从数据库加载的消息可能没有 codeContext 字段）
    if (textContent.includes('```')) {
      // 检查是否是格式：用户问题 + 换行 + 文件信息 + 代码块
      const codeBlockPattern = /\n\n(?:文件：[^\n]+(?:\n仓库：[^\n]+)?\n\n)?```/;
      const match = textContent.match(codeBlockPattern);
      if (match) {
        // 提取代码块之前的用户问题
        const userQuestion = textContent.substring(0, match.index).trim();
        // 如果提取出的问题不为空，只显示问题
        if (userQuestion) {
          return userQuestion;
        }
      }
    }
    
    return textContent;
  } catch (error) {
    console.error('解析消息文本失败:', error);
  }
  
  return '';
});

// 解析消息中的图片
const messageImages = computed(() => {
  if (!props.message || props.message.type !== 'human') return [];
  
  try {
    // 尝试从消息的 content 字段直接解析（实时消息）
    if (Array.isArray(props.message.content)) {
      const images = props.message.content
        .filter(item => item.type === 'image_url')
        .map((item, index) => ({
          url: item.image_url?.url || item.image_url,
          name: `图片 ${index + 1}`
        }));
      
      if (images.length > 0) return images;
    }
    
    // 尝试从 extra_metadata 中获取原始消息（历史消息）
    const rawMessage = props.message.extra_metadata?.raw_message;
    if (rawMessage && rawMessage.content && Array.isArray(rawMessage.content)) {
      return rawMessage.content
        .filter(item => item.type === 'image_url')
        .map((item, index) => ({
          url: item.image_url?.url || item.image_url,
          name: `图片 ${index + 1}`
        }));
    }
  } catch (error) {
    console.error('解析消息图片失败:', error);
  }
  
  return [];
});

// 解析消息中的文件
const messageFiles = computed(() => {
  if (!props.message || props.message.type !== 'human') return [];
  
  try {
    // 从 extra_metadata 中获取文件信息
    const extraMeta = props.message.extra_metadata;
    
    if (extraMeta && extraMeta.files && Array.isArray(extraMeta.files)) {
      return extraMeta.files;
    }
    
    // 也尝试从消息对象本身读取（如果extra_metadata不存在）
    if (props.message.files && Array.isArray(props.message.files)) {
      return props.message.files;
    }
  } catch (error) {
    console.error('解析消息文件失败:', error);
  }
  
  return [];
});

// 获取代码上下文
const messageCodeContext = computed(() => {
  if (!props.message || props.message.type !== 'human') return null;
  
  // 从消息对象中获取代码上下文
  if (props.message.codeContext) {
    return props.message.codeContext;
  }
  
  return null;
});

// 代码预览区域的 ref
const messageCodeRef = ref(null);

// 监听代码上下文变化，应用语法高亮
watch(messageCodeContext, async (newContext) => {
  if (newContext && messageCodeRef.value) {
    await nextTick();
    try {
      const language = newContext.language || '';
      if (language) {
        hljs.highlightElement(messageCodeRef.value);
      } else {
        messageCodeRef.value.innerHTML = hljs.highlightAuto(messageCodeRef.value.textContent).value;
      }
    } catch (error) {
      console.error('代码高亮失败:', error);
    }
  }
}, { flush: 'post', immediate: true });

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

// 图片预览
const previewImage = (img, index) => {
  // 使用 Ant Design Vue 的图片预览
  AImage.PreviewGroup.preview({
    src: img.url,
    visible: true,
    current: index
  });
};

// 文件预览模态框状态
const filePreviewVisible = ref(false);
const filePreviewTitle = ref('');
const filePreviewContent = ref('');

// 响应式模态框宽度
const filePreviewModalWidth = computed(() => {
  if (typeof window === 'undefined') return 900;
  const width = window.innerWidth;
  if (width < 768) return '95%';
  if (width < 1024) return 800;
  return 900;
});

// 文件内容预览
const previewFileContent = (file) => {
  filePreviewTitle.value = `预览：${file.name}`;
  filePreviewContent.value = file.extractedText || '';
  filePreviewVisible.value = true;
};

// 关闭文件预览
const closeFilePreview = () => {
  filePreviewVisible.value = false;
  // 延迟清空内容，避免关闭动画时内容闪烁
  setTimeout(() => {
    filePreviewTitle.value = '';
    filePreviewContent.value = '';
  }, 300);
};

// 文件可视化
const showFileVisualization = (file) => {
  emit('openRefs', file.visualizationData);
};

// 工具相关方法
const getToolNameByToolCall = (toolCall) => {
  const toolId = toolCall.name || toolCall.function.name;
  const toolsList = availableTools.value ? Object.values(availableTools.value) : [];
  const tool = toolsList.find(t => t.id === toolId);
  return tool ? tool.name : toolId;
};

const parsedData = computed(() => {
  // Start with default values from the prop to avoid mutation.
  let content = props.message.content.trim() || '';
  let reasoning_content = props.message.additional_kwargs?.reasoning_content || '';

  if (reasoning_content) {
    return {
      content,
      reasoning_content,
    }
  }

  // Regex to find <think>...</think> or an unclosed <think>... at the end of the string.
  const thinkRegex = /<think>(.*?)<\/think>|<think>(.*?)$/s;
  const thinkMatch = content.match(thinkRegex);

  if (thinkMatch) {
    // The captured reasoning is in either group 1 (closed tag) or 2 (unclosed tag).
    reasoning_content = (thinkMatch[1] || thinkMatch[2] || '').trim();
    // Remove the entire matched <think> block from the original content.
    content = content.replace(thinkMatch[0], '').trim();
  }

  return {
    content,
    reasoning_content,
  };
});

const toggleToolCall = (toolCallId) => {
  if (expandedToolCalls.value.has(toolCallId)) {
    expandedToolCalls.value.delete(toolCallId);
  } else {
    expandedToolCalls.value.add(toolCallId);
  }
};
</script>

<style lang="less" scoped>
.message-container {
  display: flex;
  flex-direction: column;
  margin: 0.8rem 0;

  // 用户消息容器样式
  &.human,
  &.sent {
    align-items: flex-end;
    max-width: 95%;
    margin-left: auto;
  }

  // 助手消息容器样式
  &.ai,
  &.assistant,
  &.received {
    align-items: flex-start;
    width: 100%;
    max-width: 100%;
  }

  // 图片显示在消息框外部（上方）
  .message-images {
    margin-bottom: 8px;
    width: 100%;
    max-width: 100%;

    .images-grid {
      display: grid;
      gap: 8px;

      &.images-count-1 {
        grid-template-columns: 1fr;
      }

      &.images-count-2 {
        grid-template-columns: repeat(2, 1fr);
      }

      &.images-count-3 {
        grid-template-columns: repeat(3, 1fr);
      }
    }

    .message-image-wrapper {
      position: relative;
      cursor: pointer;
      border-radius: 8px;
      overflow: hidden;
      background: rgba(0, 0, 0, 0.05);
      
      &:hover {
        opacity: 0.9;
      }

      .message-image {
        width: 100%;
        height: auto;
        max-height: 200px;
        object-fit: cover;
        display: block;
        border-radius: 8px;
      }
    }
  }

  // 文件显示在消息框外部（上方）
  .message-code-context {
    margin-bottom: 8px;
    width: 100%;
    max-width: 100%;
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    overflow: hidden;
    background: var(--gray-50);

    .code-context-header {
      padding: 8px 12px;
      background: white;
      border-bottom: 1px solid var(--gray-200);

      .code-context-info {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
        min-width: 0;

        .code-file-name {
          font-size: 13px;
          font-weight: 500;
          color: var(--gray-800);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .code-repo-name {
          font-size: 12px;
          color: var(--gray-500);
          padding: 2px 8px;
          background: var(--gray-100);
          border-radius: 4px;
          white-space: nowrap;
        }
      }
    }

    .code-context-content {
      max-height: 300px;
      overflow: auto;
      background: #f6f8fa;

      pre {
        margin: 0;
        padding: 12px;

        code {
          font-size: 13px;
          line-height: 1.5;
          font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
          
          &.hljs {
            background: transparent;
            padding: 0;
          }
        }
      }
    }
  }

  .message-files {
    margin-bottom: 8px;
    width: 100%;
    max-width: 100%;
    display: flex;
    flex-direction: column;
    gap: 8px;

    .message-file-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      background-color: var(--gray-50);
      border: 1px solid var(--gray-200);
      border-radius: 8px;
      transition: all 0.2s ease;

      &:hover {
        background-color: var(--gray-100);
        border-color: var(--gray-300);
      }

      .file-icon {
        font-size: 20px;
        color: var(--main-color);
        flex-shrink: 0;
      }

      .file-info {
        flex: 1;
        min-width: 0;

        .file-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--gray-800);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          margin-bottom: 4px;
        }

        .file-size {
          font-size: 12px;
          color: var(--gray-600);
        }
      }

      .preview-btn,
      .viz-btn {
        padding: 0;
        height: auto;
        font-size: 12px;
        flex-shrink: 0;
      }
    }
  }
}

.message-box {
  display: inline-block;
  border-radius: 1.5rem;
  margin: 0;
  padding: 0.625rem 1.25rem;
  user-select: text;
  word-break: break-word;
  word-wrap: break-word;
  font-size: 15px;
  line-height: 24px;
  box-sizing: border-box;
  color: black;
  max-width: 100%;
  position: relative;
  letter-spacing: .25px;

  &.human, &.sent {
    max-width: 100%;
    color: white;
    background-color: var(--main-color);
    align-self: flex-end;
    border-radius: .5rem;
    padding: 0.5rem 1rem;
  }

  &.assistant, &.received, &.ai {
    color: initial;
    width: 100%;
    text-align: left;
    margin: 0;
    padding: 0px;
    background-color: transparent;
    border-radius: 0;
  }

  .message-text {
    max-width: 100%;
    margin-bottom: 0;
    white-space: pre-line;
  }

  // 用户消息
  .human-message {
    .message-text {
      margin-bottom: 0;
    }
  }

  .err-msg {
    color: #d15252;
    border: 1px solid #f19999;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    text-align: left;
    background: #fffbfb;
    margin-bottom: 10px;
    cursor: pointer;
  }

  .searching-msg {
    color: var(--gray-700);
    animation: colorPulse 1s infinite ease-in-out;
  }

  .reasoning-box {
    margin-top: 10px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: 1px solid var(--gray-200);
    background-color: var(--gray-25);
    overflow: hidden;
    transition: all 0.2s ease;

    :deep(.ant-collapse) {
      background-color: transparent;
      border: none;

      .ant-collapse-item {
        border: none;

        .ant-collapse-header {
          padding: 8px 12px;
          // background-color: var(--gray-100);
          font-size: 14px;
          font-weight: 500;
          color: var(--gray-700);
          transition: all 0.2s ease;

          .ant-collapse-expand-icon {
            color: var(--gray-400);
          }
        }

        .ant-collapse-content {
          border: none;
          background-color: transparent;

          .ant-collapse-content-box {
            padding: 16px;
            background-color: var(--gray-25);
          }
        }
      }
    }

    .reasoning-content {
      font-size: 13px;
      color: var(--gray-800);
      white-space: pre-wrap;
      margin: 0;
      line-height: 1.6;
    }
  }

  .assistant-message {
    width: 100%;
  }

  .status-info {
    display: block;
    background-color: var(--gray-50);
    color: var(--gray-700);
    padding: 10px;
    border-radius: 8px;
    margin-bottom: 10px;
    font-size: 12px;
    font-family: monospace;
    max-height: 200px;
    overflow-y: auto;
  }

  :deep(.tool-calls-container) {
    width: 100%;
    margin-top: 10px;

    .tool-call-container {
      margin-bottom: 10px;

      &:last-child {
        margin-bottom: 0;
      }
    }
  }

  :deep(.tool-call-display) {
    background-color: var(--gray-25);
    outline: 1px solid var(--gray-200);
    border-radius: 8px;
    overflow: hidden;
    transition: all 0.2s ease;

    .tool-header {
      padding: 8px 12px;
      // background-color: var(--gray-100);
      font-size: 14px;
      font-weight: 500;
      color: var(--gray-800);
      border-bottom: 1px solid var(--gray-100);
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      user-select: none;
      position: relative;
      transition: color 0.2s ease;
      align-items: center;

      .anticon {
        color: var(--main-color);
        font-size: 16px;
      }

      .tool-name {
        font-weight: 600;
        color: var(--main-700);
      }

      span {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .tool-loader {
        margin-top: 2px;
        color: var(--main-700);
      }

      .tool-loader.rotate {
        animation: rotate 2s linear infinite;
      }

      .tool-loader.tool-success {
        color: var(--color-success);
      }

      .tool-loader.tool-error {
        color: var(--color-error);
      }

      .tool-loader.tool-loading {
        color: var(--color-info);
      }
    }

    .tool-content {
      transition: all 0.3s ease;

      .tool-params {
        padding: 8px 12px;
        background-color: var(--gray-25);
        border-bottom: 1px solid var(--gray-150);

        .tool-params-content {
          margin: 0;
          font-size: 13px;
          overflow-x: auto;
          color: var(--gray-700);
          line-height: 1.5;

          pre {
            margin: 0;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          }
        }
      }

      .tool-result {
        padding: 0;
        background-color: transparent;

        .tool-result-header {
          padding: 12px 16px;
          background-color: var(--gray-100);
          font-size: 12px;
          color: var(--gray-700);
          font-weight: 500;
          border-bottom: 1px solid var(--gray-200);
        }

        .tool-result-content {
          padding: 0;
          background-color: transparent;
        }
      }
    }

    &.is-collapsed {
      .tool-header {
        border-bottom: none;
      }
    }
  }
}

.retry-hint {
  margin-top: 8px;
  padding: 8px 16px;
  color: #666;
  font-size: 14px;
  text-align: left;
}

.retry-link {
  color: #1890ff;
  cursor: pointer;
  margin-left: 4px;

  &:hover {
    text-decoration: underline;
  }
}

.ant-btn-icon-only {
  &:has(.anticon-stop) {
    background-color: #ff4d4f !important;

    &:hover {
      background-color: #ff7875 !important;
    }
  }
}

@keyframes colorPulse {
  0% { color: var(--gray-700); }
  50% { color: var(--gray-300); }
  100% { color: var(--gray-700); }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

<style lang="less" scoped>
:deep(.message-md) {
  margin: 8px 0;
}

:deep(.message-md .md-editor-preview-wrapper) {
  max-width: 100%;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans SC', 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Source Han Sans CN', 'Courier New', monospace;

  #preview-only-preview {
    font-size: 1rem;
    line-height: 1.75;
    color: var(--gray-1000);
  }


  h1, h2 {
    font-size: 1.2rem;
  }

  h3, h4 {
    font-size: 1.1rem;
  }

  h5, h6 {
    font-size: 1rem;
  }

  strong {
    font-weight: 500;
  }

  li > p, ol > p, ul > p {
    margin: 0.25rem 0;
  }

  ul li::marker,
  ol li::marker {
    color: var(--main-bright);
  }

  ul, ol {
    padding-left: 1.625rem;
  }

  cite {
    font-size: 12px;
    color: var(--gray-700);
    font-style: normal;
    background-color: var(--gray-200);
    border-radius: 4px;
    outline: 2px solid var(--gray-200);
  }

  a {
    color: var(--main-700);
  }

  .md-editor-code {
    border: var(--gray-50);
    border-radius: 8px;

    .md-editor-code-head {
      background-color: var(--gray-50);

      .md-editor-collapse-tips {
        color: var(--gray-400);
      }
    }
  }

  code {
    font-size: 13px;
    font-family: 'Menlo', 'Monaco', 'Consolas', 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', 'Hiragino Sans GB', 'Source Han Sans CN', 'Courier New', monospace;
    line-height: 1.5;
    letter-spacing: 0.025em;
    tab-size: 4;
    -moz-tab-size: 4;
    background-color: var(--gray-25);
  }

  p:last-child {
    margin-bottom: 0;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 2em 0;
    font-size: 15px;
    display: table;
    outline: 1px solid var(--gray-100);
    outline-offset: 14px;
    border-radius: 12px;

    thead tr th{
      padding-top: 0;
    }

    thead th,
    tbody th {
      border: none;
      border-bottom: 1px solid var(--gray-200);
    }

    tbody tr:last-child td {
      border-bottom: 1px solid var(--gray-200);
      border: none;
      padding-bottom: 0;
    }
  }

  th,
  td {
    padding: 0.5rem 0rem;
    text-align: left;
    border: none;
  }

  td {
    border-bottom: 1px solid var(--gray-100);
    color: var(--gray-800);
  }

  th {
    font-weight: 600;
    color: var(--gray-800);
  }

  tr {
    background-color: var(--gray-0);
  }

  // tbody tr:last-child td {
  //   border-bottom: none;
  // }
}

:deep(.chat-box.font-smaller #preview-only-preview) {
  font-size: 14px;

  h1, h2 {
    font-size: 1.1rem;
  }

  h3, h4 {
    font-size: 1rem;
  }
}

:deep(.chat-box.font-larger #preview-only-preview) {
  font-size: 16px;

  h1, h2 {
    font-size: 1.3rem;
  }

  h3, h4 {
    font-size: 1.2rem;
  }

  h5, h6 {
    font-size: 1.1rem;
  }

  code {
    font-size: 14px;
  }
}

// 文件预览模态框样式
:deep(.file-preview-modal) {
  .ant-modal-content {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  }

  .ant-modal-header {
    background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    padding: 20px 24px;

    .ant-modal-title {
      font-size: 18px;
      font-weight: 600;
      color: #1a1a1a;
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }

  .ant-modal-body {
    padding: 0;
  }

  .ant-modal-footer {
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    padding: 16px 24px;
    background: #fafafa;
  }
}

.file-preview-modal-content {
  min-height: 400px;
  max-height: 70vh;
  overflow-y: auto;
  padding: 24px;
  background: #ffffff;

  .markdown-preview {
    :deep(.md-editor-preview-wrapper) {
      background: transparent;
      padding: 0;
    }

    :deep(.md-editor-preview) {
      font-size: 14px;
      line-height: 1.8;
      color: #333;

      h1, h2, h3, h4, h5, h6 {
        margin-top: 24px;
        margin-bottom: 16px;
        font-weight: 600;
        line-height: 1.25;
        color: #1a1a1a;
      }

      h1 {
        font-size: 24px;
        border-bottom: 1px solid #eaecef;
        padding-bottom: 8px;
      }

      h2 {
        font-size: 20px;
        border-bottom: 1px solid #eaecef;
        padding-bottom: 8px;
      }

      h3 {
        font-size: 18px;
      }

      h4 {
        font-size: 16px;
      }

      p {
        margin-bottom: 16px;
        word-wrap: break-word;
      }

      ul, ol {
        margin-bottom: 16px;
        padding-left: 24px;

        li {
          margin-bottom: 8px;
        }
      }

      code {
        background: #f6f8fa;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 13px;
        font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', monospace;
      }

      pre {
        background: #f6f8fa;
        border-radius: 6px;
        padding: 16px;
        overflow-x: auto;
        margin-bottom: 16px;

        code {
          background: transparent;
          padding: 0;
        }
      }

      blockquote {
        border-left: 4px solid #dfe2e5;
        padding-left: 16px;
        margin: 16px 0;
        color: #6a737d;
      }

      table {
        border-collapse: collapse;
        margin-bottom: 16px;
        width: 100%;

        th, td {
          border: 1px solid #dfe2e5;
          padding: 8px 12px;
        }

        th {
          background: #f6f8fa;
          font-weight: 600;
        }
      }

      hr {
        border: none;
        border-top: 1px solid #eaecef;
        margin: 24px 0;
      }

      a {
        color: #0366d6;
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }

      img {
        max-width: 100%;
        height: auto;
        border-radius: 6px;
        margin: 16px 0;
      }
    }
  }

  .empty-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    color: #8c8c8c;
    font-size: 14px;
    gap: 12px;

    .anticon {
      font-size: 48px;
      color: #d9d9d9;
    }
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

// 响应式设计
@media (max-width: 768px) {
  .file-preview-modal-content {
    padding: 16px;
    max-height: 60vh;

    .markdown-preview {
      :deep(.md-editor-preview) {
        font-size: 13px;

        h1 {
          font-size: 20px;
        }

        h2 {
          font-size: 18px;
        }

        h3 {
          font-size: 16px;
        }
      }
    }
  }
}
</style>