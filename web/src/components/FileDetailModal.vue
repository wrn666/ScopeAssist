<template>
  <a-modal
    v-model:open="visible"
    width="95%"
    :footer="null"
    wrap-class-name="file-detail-fullscreen"
    @after-open-change="afterOpenChange"
    :bodyStyle="{ height: 'calc(90vh - 110px)', padding: '0', overflow: 'hidden' }"
    :maskClosable="false"
    :closable="true"
    :centered="true"
  >
    <template #title>
      <div class="modal-header">
        <!-- 面包屑导航 -->
        <div class="breadcrumb-section">
          <a-breadcrumb>
            <a-breadcrumb-item>数据集</a-breadcrumb-item>
            <a-breadcrumb-item>{{ store.database?.name || '知识库' }}</a-breadcrumb-item>
            <a-breadcrumb-item>{{ file?.filename || '文件详情' }}</a-breadcrumb-item>
          </a-breadcrumb>
        </div>
        <!-- 标题区域：左右两个部分 -->
        <div class="header-content">
          <!-- 左侧：文件信息 -->
          <div class="file-info-header">
            <div class="file-name-section">
              <FileTextOutlined class="file-icon" />
              <span class="file-name">{{ file?.filename || '文件详情' }}</span>
            </div>
            <div class="file-meta">
              <span v-if="file?.file_size">
                大小: {{ formatFileSize(file.file_size) }}
              </span>
              <span v-if="file?.created_at" class="meta-item">
                <span class="meta-separator" v-if="file?.file_size">|</span>
                上传时间: {{ formatStandardTime(file.created_at) }}
              </span>
              <span v-if="showVisualizationButton" class="visualize-btn-wrapper">
                <a-button
                  type="primary"
                  size="small"
                  @click="handleShowVisualization"
                  :loading="visualizationLoading"
                  class="visualize-btn"
                >
                  <EyeOutlined /> 可视化
                </a-button>
              </span>
            </div>
          </div>
          <!-- 右侧：Chunk 结果标题 -->
          <div class="chunk-info-header" v-if="file?.lines && file.lines.length > 0">
            <h3 class="chunk-title">Chunk 结果</h3>
            <p class="chunk-description">查看用于嵌入和检索的片段。</p>
          </div>
        </div>
      </div>
    </template>

    <div class="file-detail-layout" v-if="file">
      <!-- 左侧文件内容区域 -->
      <div class="file-content-panel">
        <div v-if="loading" class="loading-container">
          <a-spin size="large" />
          <p>正在加载文件内容...</p>
        </div>

        <div v-else-if="file.lines && file.lines.length > 0" class="content-section">
          <!-- 隐藏MarkdownContentViewer自带的chunk面板 -->
          <div class="markdown-wrapper">
            <MarkdownContentViewer :chunks="file.lines" />
          </div>
        </div>

        <div v-else class="empty-content">
          <InboxOutlined class="empty-icon" />
          <p>暂无文件内容</p>
          <p class="empty-hint">文件可能尚未处理完成，请稍后再试</p>
        </div>
      </div>

      <!-- 右侧Chunk Result面板 -->
      <div class="chunk-result-panel" v-if="file.lines && file.lines.length > 0">
        <div class="chunk-panel-controls">
          <div class="action-buttons-group">
            <a-checkbox v-model:checked="selectAll" @change="handleSelectAll">全选</a-checkbox>
            <a-button size="small" @click="handleEnableChunks">启用</a-button>
            <a-button size="small" @click="handleDisableChunks">禁用</a-button>
            <a-button size="small" danger @click="handleDeleteChunks">删除</a-button>
          </div>

          <div class="search-box">
            <a-input-search
              v-model:value="searchQuery"
              placeholder="搜索"
              size="small"
              @search="handleSearch"
            />
          </div>
        </div>

        <div class="chunk-list-container">
          <div
            v-for="(chunk, index) in filteredChunks"
            :key="getChunkId(chunk) || index"
            class="chunk-card"
            :class="{ selected: selectedChunks.includes(getChunkId(chunk) || getChunkGlobalIndex(index)) }"
          >
            <div class="chunk-card-header">
              <a-checkbox
                :checked="selectedChunks.includes(getChunkId(chunk) || getChunkGlobalIndex(index))"
                @change="(e) => handleChunkSelect(getChunkId(chunk) || getChunkGlobalIndex(index), e.target.checked)"
                @click.stop
              />
              <div class="chunk-title" @click="toggleChunkExpand(getChunkGlobalIndex(index))">
                <span class="title-text">
                  Chunk {{ getChunkGlobalIndex(index) + 1 }}: {{ getChunkPreview(chunk.content || chunk.text || '', 200) }}
                </span>
                <span class="title-answer" v-if="getChunkAnswer(chunk)">
                  答案: {{ getChunkAnswerText(chunk) }}
                </span>
              </div>
              <a-switch
                :checked="getChunkEnabled(chunk)"
                size="small"
                @change="handleToggleChunkEnabled(chunk, $event)"
                @click.stop
              />
            </div>
            <div class="chunk-card-content" v-show="expandedChunks.includes(getChunkGlobalIndex(index))">
              <div class="chunk-content-text">
                <MdPreview
                  :modelValue="chunk.content || chunk.text || ''"
                  theme="light"
                  previewTheme="github"
                  codeTheme="atom"
                  :showCodeRowNumber="false"
                />
              </div>
              <div class="chunk-actions">
                <a-button size="small" @click="handleEditChunk(chunk)">编辑</a-button>
              </div>
            </div>
          </div>
        </div>

        <div class="chunk-panel-footer">
          <span class="footer-text">总计 {{ searchedChunks.length }}</span>
          <div class="pagination-controls">
            <a-button size="small" :disabled="currentPage === 1" @click="currentPage--">‹</a-button>
            <span class="page-info">第 {{ currentPage }} 页，共 {{ totalPages }} 页</span>
            <a-button size="small" :disabled="currentPage >= totalPages" @click="currentPage++">›</a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit Chunk Modal -->
    <a-modal
      v-model:open="editChunkModalVisible"
      title="编辑片段"
      width="800px"
      @cancel="handleCancelEdit"
    >
      <div class="edit-chunk-form">
        <div class="form-section">
          <label class="form-label">片段内容</label>
          <a-textarea
            v-model:value="editingChunk.content"
            :rows="12"
            placeholder="请输入片段内容"
          />
        </div>

        <div class="form-section">
          <label class="form-label">关键词</label>
          <div class="tag-input-group">
            <a-tag
              v-for="(keyword, idx) in editingChunk.keywords"
              :key="idx"
              closable
              @close="removeKeyword(idx)"
            >
              {{ keyword }}
            </a-tag>
            <a-input
              v-if="keywordInputVisible"
              ref="keywordInputRef"
              v-model:value="keywordInput"
              size="small"
              style="width: 100px"
              @blur="handleKeywordInputConfirm"
              @keyup.enter="handleKeywordInputConfirm"
            />
            <a-tag v-else style="background: #fff; border-style: dashed; cursor: pointer" @click="showKeywordInput">
              <PlusOutlined /> 添加
            </a-tag>
          </div>
        </div>

        <div class="form-section">
          <label class="form-label">
            问题
            <a-tooltip title="添加与此片段相关的问题">
              <InfoCircleOutlined style="margin-left: 4px; color: #999" />
            </a-tooltip>
          </label>
          <div class="question-list">
            <div
              v-for="(question, idx) in editingChunk.questions"
              :key="idx"
              class="question-item"
            >
              <a-input
                v-model:value="editingChunk.questions[idx]"
                placeholder="请输入问题"
              />
              <a-button
                type="text"
                danger
                @click="removeQuestion(idx)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
            <a-button
              type="dashed"
              block
              @click="addQuestion"
              style="margin-top: 8px"
            >
              <PlusOutlined /> 添加问题
            </a-button>
          </div>
        </div>

        <div class="form-section">
          <label class="form-label">标签</label>
          <div class="tag-input-group">
            <a-tag
              v-for="(tag, idx) in editingChunk.tags"
              :key="idx"
              closable
              @close="removeTag(idx)"
            >
              {{ tag }}
            </a-tag>
            <a-input
              v-if="tagInputVisible"
              ref="tagInputRef"
              v-model:value="tagInput"
              size="small"
              style="width: 100px"
              @blur="handleTagInputConfirm"
              @keyup.enter="handleTagInputConfirm"
            />
            <a-tag v-else style="background: #fff; border-style: dashed; cursor: pointer" @click="showTagInput">
              <PlusOutlined /> 添加标签
            </a-tag>
          </div>
        </div>

        <div class="form-section">
          <label class="form-label">启用</label>
          <a-switch v-model:checked="editingChunk.enabled" />
        </div>
      </div>

      <template #footer>
        <a-button @click="handleCancelEdit">取消</a-button>
        <a-button type="primary" @click="handleSaveChunk" :loading="savingChunk">确认</a-button>
      </template>
    </a-modal>
  </a-modal>

  <!-- Unstructured 可视化弹窗 -->
  <UnstructuredVisualizerModal
    v-model:visible="visualizerModalVisible"
    :pre-loaded-data="visualizationData"
  />
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { message, Modal } from 'ant-design-vue';
import {
  EyeOutlined,
  FileTextOutlined,
  InboxOutlined,
  PlusOutlined,
  DeleteOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue';
import { useDatabaseStore } from '@/stores/database';
import { agentApi } from '@/apis/agent_api';
import { documentApi } from '@/apis/knowledge_api';
import MarkdownContentViewer from './MarkdownContentViewer.vue';
import UnstructuredVisualizerModal from './UnstructuredVisualizerModal.vue';
import { getStatusText, formatStandardTime } from '@/utils/file_utils';
import { MdPreview } from 'md-editor-v3';
import 'md-editor-v3/lib/preview.css';

const store = useDatabaseStore();

const visible = computed({
  get: () => store.state.fileDetailModalVisible,
  set: (value) => store.state.fileDetailModalVisible = value
});

const file = computed(() => store.selectedFile);
const loading = computed(() => store.state.fileDetailLoading);

// 可视化相关
const visualizerModalVisible = ref(false);
const visualizationData = ref(null);
const visualizationLoading = ref(false);

// Chunk Result面板相关
const selectAll = ref(false);
const selectedChunks = ref([]);
const searchQuery = ref('');
const currentPage = ref(1);
const pageSize = ref(50);
const expandedChunks = ref([]);

// Edit Chunk Modal相关
const editChunkModalVisible = ref(false);
const savingChunk = ref(false);
const editingChunk = ref({
  id: null,
  content: '',
  keywords: [],
  questions: [],
  tags: [],
  enabled: true
});
const keywordInputVisible = ref(false);
const keywordInput = ref('');
const keywordInputRef = ref(null);
const tagInputVisible = ref(false);
const tagInput = ref('');
const tagInputRef = ref(null);

// 判断是否显示可视化按钮
const showVisualizationButton = computed(() => {
  if (!file.value || !file.value.filename) return false;
  // 只对 PDF 文件显示可视化按钮
  return file.value.filename.toLowerCase().endsWith('.pdf');
});

const afterOpenChange = (open) => {
  if (!open) {
    store.selectedFile = null;
    visualizationData.value = null;
  }
};

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '-';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
};

// 处理可视化
const handleShowVisualization = async () => {
  // 从 path 字段获取文件路径
  const filePath = file.value?.path;

  if (!filePath) {
    console.error('文件对象：', file.value);
    message.error('无法获取文件路径，请联系管理员');
    return;
  }

  visualizationLoading.value = true;

  try {
    message.info('正在加载可视化数据，这可能需要一些时间...');

    // 通过文件路径获取可视化数据
    const result = await agentApi.visualizeUnstructuredByPath(filePath);

    // 设置数据并打开可视化弹窗
    visualizationData.value = result;
    visualizerModalVisible.value = true;

    message.success('可视化数据加载成功');

  } catch (error) {
    console.error('加载可视化数据失败:', error);
    message.error('加载可视化数据失败: ' + error.message);
  } finally {
    visualizationLoading.value = false;
  }
};

// 计算搜索过滤后的chunks（不分页）
const searchedChunks = computed(() => {
  let chunks = file.value?.lines || [];

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    chunks = chunks.filter(chunk => {
      const content = (chunk.content || chunk.text || '').toLowerCase();
      const question = (getChunkQuestion(chunk) || '').toLowerCase();
      const answer = (getChunkAnswer(chunk) || '').toLowerCase();
      return content.includes(query) || question.includes(query) || answer.includes(query);
    });
  }

  return chunks;
});

// 计算分页后的chunks
const filteredChunks = computed(() => {
  const chunks = searchedChunks.value;

  // 分页
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return chunks.slice(start, end);
});

// 总页数（基于搜索后的结果）
const totalPages = computed(() => {
  const total = searchedChunks.value.length;
  return Math.ceil(total / pageSize.value);
});

// 获取chunk的ID（优先使用chunk_id）
const getChunkId = (chunk) => {
  return chunk.chunk_id || chunk.id;
};

// 获取chunk的全局索引
const getChunkGlobalIndex = (chunkIndex) => {
  const start = (currentPage.value - 1) * pageSize.value;
  return start + chunkIndex;
};

// 获取chunk预览
const getChunkPreview = (content, maxLength = 100) => {
  if (!content) return '';
  if (content.length <= maxLength) return content;
  return content.substring(0, maxLength) + '...';
};

// 获取chunk标题显示文本
const getChunkTitleText = (chunk, index) => {
  const question = getChunkQuestion(chunk);
  if (question) {
    return question;
  }
  const preview = getChunkPreview(chunk.content || chunk.text || '', 60);
  return `${index}. ${preview}`;
};

// 获取chunk答案显示文本
const getChunkAnswerText = (chunk) => {
  const answer = getChunkAnswer(chunk);
  if (!answer) return '';
  return answer;
};

// 获取chunk的question（从chunk数据中提取）
const getChunkQuestion = (chunk) => {
  if (chunk.question) return chunk.question;
  if (chunk.questions && chunk.questions.length > 0) return chunk.questions[0];
  return null;
};

// 获取chunk的answer（从chunk数据中提取）
const getChunkAnswer = (chunk) => {
  if (chunk.answer) return chunk.answer;
  if (chunk.keyword) return chunk.keyword;
  if (chunk.keywords && chunk.keywords.length > 0) return chunk.keywords[0];
  return null;
};

// 获取chunk的enabled状态（使用computed使其响应式）
const getChunkEnabled = (chunk) => {
  if (chunk.enabled === undefined) {
    chunk.enabled = true;
  }
  return chunk.enabled;
};

// 切换chunk展开/折叠
const toggleChunkExpand = (globalIndex) => {
  const idx = expandedChunks.value.indexOf(globalIndex);
  if (idx > -1) {
    expandedChunks.value.splice(idx, 1);
  } else {
    expandedChunks.value.push(globalIndex);
  }
};

// 处理全选
const handleSelectAll = (e) => {
  if (e.target.checked) {
    selectedChunks.value = filteredChunks.value.map((chunk, index) => getChunkId(chunk) || getChunkGlobalIndex(index));
  } else {
    selectedChunks.value = [];
  }
};

// 处理单个chunk选择
const handleChunkSelect = (chunkId, checked) => {
  if (checked) {
    if (!selectedChunks.value.includes(chunkId)) {
      selectedChunks.value.push(chunkId);
    }
  } else {
    selectedChunks.value = selectedChunks.value.filter(id => id !== chunkId);
  }
  // 更新全选状态
  selectAll.value = selectedChunks.value.length === filteredChunks.value.length && filteredChunks.value.length > 0;
};

// 处理搜索
const handleSearch = (value) => {
  searchQuery.value = value;
  currentPage.value = 1;
};

// 处理启用chunks
const handleEnableChunks = async () => {
  if (selectedChunks.value.length === 0) {
    message.warning('请先选择要启用的片段');
    return;
  }
  // TODO: 实现启用逻辑
  message.info(`已启用 ${selectedChunks.value.length} 个片段`);
};

// 处理禁用chunks
const handleDisableChunks = async () => {
  if (selectedChunks.value.length === 0) {
    message.warning('请先选择要禁用的片段');
    return;
  }
  // TODO: 实现禁用逻辑
  message.info(`已禁用 ${selectedChunks.value.length} 个片段`);
};

// 处理删除chunks
const handleDeleteChunks = () => {
  if (selectedChunks.value.length === 0) {
    message.warning('请先选择要删除的片段');
    return;
  }
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除 ${selectedChunks.value.length} 个片段吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      // TODO: 实现删除逻辑
      message.success(`已删除 ${selectedChunks.value.length} 个片段`);
      selectedChunks.value = [];
      selectAll.value = false;
    }
  });
};

// 切换chunk的enabled状态
const handleToggleChunkEnabled = async (chunk, enabled) => {
  chunk.enabled = enabled;
  // TODO: 实现启用/禁用逻辑 - 调用API保存状态
  // await documentApi.updateChunkEnabled(store.databaseId, file.value.file_id, chunk.id, enabled);
};

// 编辑chunk
const handleEditChunk = (chunk) => {
  // 确保获取正确的chunk ID（优先使用chunk_id，因为这是后端返回的标准字段）
  const chunkId = chunk.chunk_id || chunk.id;
  if (!chunkId) {
    message.error('无法获取片段ID');
    return;
  }
  
  editingChunk.value = {
    id: chunkId,
    content: chunk.content || chunk.text || '',
    keywords: chunk.keywords || (chunk.keyword ? [chunk.keyword] : []),
    questions: chunk.questions || (chunk.question ? [chunk.question] : []),
    tags: chunk.tags || [],
    enabled: chunk.enabled !== undefined ? chunk.enabled : true
  };
  editChunkModalVisible.value = true;
};

// 取消编辑
const handleCancelEdit = () => {
  editChunkModalVisible.value = false;
  editingChunk.value = {
    id: null,
    content: '',
    keywords: [],
    questions: [],
    tags: [],
    enabled: true
  };
};

// 保存chunk
const handleSaveChunk = async () => {
  if (!editingChunk.value.content || !editingChunk.value.content.trim()) {
    message.error('片段内容不能为空');
    return;
  }

  if (!editingChunk.value.id || !file.value?.file_id || !store.databaseId) {
    message.error('缺少必要参数');
    return;
  }

  savingChunk.value = true;
  try {
    // 更新chunk内容
    await documentApi.updateChunkContent(
      store.databaseId,
      file.value.file_id,
      editingChunk.value.id,
      editingChunk.value.content.trim()
    );

    // 更新本地数据
    const chunk = file.value.lines?.find(c => {
      const cId = c.chunk_id || c.id;
      return cId === editingChunk.value.id;
    });
    if (chunk) {
      chunk.content = editingChunk.value.content.trim();
      chunk.text = editingChunk.value.content.trim();
      // 注意：keywords, questions, tags, enabled 等字段需要后端API支持才能保存
      // 目前API只支持更新content，这些字段暂时保存到本地对象中
      if (editingChunk.value.keywords && editingChunk.value.keywords.length > 0) {
        chunk.keywords = [...editingChunk.value.keywords];
        chunk.keyword = editingChunk.value.keywords[0];
      }
      if (editingChunk.value.questions && editingChunk.value.questions.length > 0) {
        chunk.questions = [...editingChunk.value.questions];
        chunk.question = editingChunk.value.questions[0];
      }
      if (editingChunk.value.tags && editingChunk.value.tags.length > 0) {
        chunk.tags = [...editingChunk.value.tags];
      }
      chunk.enabled = editingChunk.value.enabled;
    }

    message.success('片段保存成功');
    editChunkModalVisible.value = false;
    
    // 重新加载文件信息以获取最新数据
    try {
      const data = await documentApi.getDocumentInfo(store.databaseId, file.value.file_id);
      if (data.lines) {
        file.value.lines = data.lines;
      }
    } catch (error) {
      console.warn('重新加载文件信息失败:', error);
    }
  } catch (error) {
    console.error('保存chunk失败:', error);
    const errorMsg = error?.response?.data?.detail || error?.message || '未知错误';
    message.error('保存失败: ' + errorMsg);
  } finally {
    savingChunk.value = false;
  }
};

// Keyword相关
const showKeywordInput = () => {
  keywordInputVisible.value = true;
  keywordInput.value = '';
};

const handleKeywordInputConfirm = () => {
  if (keywordInput.value && !editingChunk.value.keywords.includes(keywordInput.value)) {
    editingChunk.value.keywords.push(keywordInput.value);
  }
  keywordInputVisible.value = false;
  keywordInput.value = '';
};

const removeKeyword = (index) => {
  editingChunk.value.keywords.splice(index, 1);
};

// Tag相关
const showTagInput = () => {
  tagInputVisible.value = true;
  tagInput.value = '';
};

const handleTagInputConfirm = () => {
  if (tagInput.value && !editingChunk.value.tags.includes(tagInput.value)) {
    editingChunk.value.tags.push(tagInput.value);
  }
  tagInputVisible.value = false;
  tagInput.value = '';
};

const removeTag = (index) => {
  editingChunk.value.tags.splice(index, 1);
};

// Question相关
const addQuestion = () => {
  editingChunk.value.questions.push('');
};

const removeQuestion = (index) => {
  editingChunk.value.questions.splice(index, 1);
};

// 监听搜索和分页变化，重置全选状态
watch([searchQuery, currentPage], () => {
  selectAll.value = false;
  selectedChunks.value = [];
  expandedChunks.value = [];
});
</script>

<style lang="less" scoped>
// 模态框头部
.modal-header {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 12px;
  padding-right: 8px;

  .breadcrumb-section {
    width: 100%;

    :deep(.ant-breadcrumb) {
      font-size: 13px;
    }
  }

  .header-content {
    display: flex;
    width: 100%;
    gap: 24px;
    align-items: flex-start;
  }

  .file-info-header {
    flex: 4;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    min-width: 0;

    .file-name-section {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 0;

      .file-icon {
        font-size: 18px;
        color: var(--main-color);
        flex-shrink: 0;
      }

      .file-name {
        font-size: 25px;
        font-weight: 600;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--gray-800);
      }
    }

    .file-meta {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--gray-600);
      flex-shrink: 0;

      .meta-separator {
        margin: 0 8px;
        color: var(--gray-400);
      }

      .meta-item {
        display: flex;
        align-items: center;
      }

      .visualize-btn-wrapper {
        margin-left: 8px;
        display: flex;
        align-items: center;
      }
    }
  }

  .chunk-info-header {
    flex: 5;
    display: flex;
    flex-direction: column;
    gap: 4px;

    .chunk-title {
      font-size: 18px;
      font-weight: 600;
      margin: 0;
      color: var(--gray-800);
    }

    .chunk-description {
      font-size: 12px;
      color: var(--gray-600);
      margin: 0;
      line-height: 1.5;
    }
  }
}

// 主布局
.file-detail-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
  background-color: #fff;
}

// 左侧文件内容区域
.file-content-panel {
  flex: 4;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: #fff;

  .content-section {
    flex: 1;
    overflow: hidden;
    height: 100%;

    .markdown-wrapper {
      height: 100%;
      overflow: hidden;

      // 隐藏MarkdownContentViewer自带的chunk面板
      :deep(.chunk-panel) {
        display: none;
      }

      // 调整内容面板宽度
      :deep(.viewer-container) {
        display: flex;
      }

      :deep(.content-panel) {
        flex: 1;
        width: 100%;
      }

      :deep(.viewer-header) {
        display: none;
      }
    }
  }

  .loading-container {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100%;
    gap: 16px;
    color: var(--gray-500);

    p {
      margin: 0;
      font-size: 14px;
    }
  }

  .empty-content {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100%;
    padding: 40px;
    color: var(--gray-500);

    .empty-icon {
      font-size: 64px;
      color: var(--gray-300);
      margin-bottom: 16px;
    }

    p {
      margin: 8px 0;
      font-size: 14px;
    }

    .empty-hint {
      font-size: 12px;
      color: var(--gray-400);
    }
  }
}

// 右侧Chunk Result面板
.chunk-result-panel {
  flex: 5;
  min-width: 500px;
  background-color: var(--gray-50);
  border-left: 1px solid var(--gray-200);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;

  .chunk-panel-controls {
    padding: 16px 16px 12px 16px;
    border-bottom: 1px solid var(--gray-200);
    background-color: #fff;
    display: flex;
    flex-direction: column;
    gap: 12px;

    .action-buttons-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .search-box {
      width: 100%;
    }
  }

  .chunk-list-container {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
    background-color: #fff;

    .chunk-card {
      margin-bottom: 12px;
      border: 1px solid var(--gray-200);
      border-radius: 6px;
      background-color: #fff;
      transition: all 0.2s ease;

      &:hover {
        border-color: var(--main-color);
      }

      &.selected {
        border-color: var(--main-color);
        background-color: var(--main-5);
      }

      .chunk-card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        cursor: pointer;

        .chunk-title {
          flex: 1;
          min-width: 0;

          .title-text {
            font-size: 13px;
            font-weight: 500;
            color: var(--gray-800);
            margin-bottom: 4px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: normal;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 4;
            line-clamp: 4;
            -webkit-box-orient: vertical;
          }

          .title-answer {
            display: block;
            font-size: 12px;
            color: var(--gray-600);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
      }

      .chunk-card-content {
        padding: 12px;
        border-top: 1px solid var(--gray-100);
        background-color: var(--gray-50);

        .chunk-content-text {
          margin-bottom: 12px;
          max-height: 700px;
          overflow-y: auto;

          :deep(.md-editor-preview) {
            padding: 0;
            font-size: 13px;
            line-height: 1.6;
          }

          :deep(.md-editor-preview-wrapper) {
            padding: 0;
          }

          :deep(pre) {
            margin: 8px 0;
            padding: 12px;
            background-color: var(--gray-50);
            border-radius: 4px;
            overflow-x: auto;
          }

          :deep(code) {
            font-size: 12px;
          }

          :deep(p) {
            margin: 8px 0;
          }

          :deep(ul), :deep(ol) {
            margin: 8px 0;
            padding-left: 24px;
          }

          :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
            margin: 12px 0 8px 0;
            font-weight: 600;
          }

          :deep(blockquote) {
            margin: 8px 0;
            padding: 8px 16px;
            border-left: 4px solid var(--main-color);
            background-color: var(--gray-50);
          }

          :deep(table) {
            width: 100%;
            margin: 8px 0;
            border-collapse: collapse;
          }

          :deep(table th), :deep(table td) {
            padding: 8px;
            border: 1px solid var(--gray-200);
          }
        }

        .chunk-actions {
          display: flex;
          justify-content: flex-end;
        }
      }
    }
  }

  .chunk-panel-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--gray-200);
    background-color: #fff;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;

    .footer-text {
      font-size: 13px;
      color: var(--gray-700);
    }

    .pagination-controls {
      display: flex;
      align-items: center;
      gap: 8px;

      .page-info {
        font-size: 12px;
        color: var(--gray-600);
      }
    }
  }
}

// Edit Chunk Modal样式
.edit-chunk-form {
  .form-section {
    margin-bottom: 24px;

    .form-label {
      display: block;
      font-size: 14px;
      font-weight: 500;
      color: var(--gray-800);
      margin-bottom: 8px;
    }

    .tag-input-group {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }

    .question-list {
      .question-item {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;

        .ant-input {
          flex: 1;
        }
      }
    }
  }
}
</style>

<style lang="less">
.file-detail-fullscreen {
  .ant-modal {
    max-width: 95%;
    padding-bottom: 0;
    margin: 0 auto;
  }

  .ant-modal-content {
    display: flex;
    flex-direction: column;
    height: 90vh;
    max-height: 90vh;
  }

  .ant-modal-header {
    flex-shrink: 0;
    padding: 16px 24px;
    border-bottom: none;
  }

  .ant-modal-body {
    flex: 1;
    overflow: hidden;
    padding: 0;
    min-height: 0;
  }
}
</style>
