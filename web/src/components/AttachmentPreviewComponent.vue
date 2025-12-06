<template>
  <div class="attachment-preview" v-if="attachments.length > 0">
    <div class="preview-header">
      <span class="preview-title">已选择 {{ attachments.length }} 个附件</span>
      <a-button type="link" size="small" @click="clearAll">
        清空全部
      </a-button>
    </div>
    <div class="preview-grid">
      <div 
        v-for="(item, index) in attachments" 
        :key="index"
        class="preview-item"
        :class="{ 'is-image': item.type === 'image' }"
      >
        <!-- 图片预览 -->
        <div v-if="item.type === 'image'" class="image-wrapper">
          <a-image 
            :src="item.preview" 
            :alt="item.name" 
            class="preview-image"
            :preview="{
              mask: '点击预览'
            }"
          />
          <div class="image-overlay">
            <a-button 
              type="text" 
              size="small" 
              class="remove-btn"
              @click.stop="removeItem(index)"
            >
              <CloseOutlined />
            </a-button>
          </div>
        </div>
        
        <!-- 文件预览 -->
        <div v-else class="file-wrapper" :class="{ 'is-extracting': item.extracting, 'has-error': item.error }">
          <div class="file-icon">
            <LoadingOutlined v-if="item.extracting" spin />
            <ExclamationCircleOutlined v-else-if="item.error" />
            <CheckCircleOutlined v-else-if="item.extractedText" />
            <FileOutlined v-else />
          </div>
          <div class="file-info">
            <div class="file-name" :title="item.name">{{ item.name }}</div>
            <div class="file-status">
              <span v-if="item.extracting" class="status-text">提取中...</span>
              <span v-else-if="item.error" class="status-text error">{{ item.error }}</span>
              <span v-else-if="item.extractedText" class="status-text success">已提取</span>
              <span v-else class="file-size">{{ formatSize(item.size) }}</span>
              <a-button
                v-if="item.extractedText"
                type="link"
                size="small"
                @click="openPreview(item)"
                class="preview-btn"
              >
                <EyeOutlined /> 预览内容
              </a-button>
              <a-button
                v-if="item.hasVisualization && item.extractedText"
                type="link"
                size="small"
                @click="showVisualization(item.visualizationData)"
                class="viz-btn"
              >
                <FileSearchOutlined /> 可视化
              </a-button>
            </div>
          </div>
          <a-button 
            type="text" 
            size="small" 
            class="remove-btn"
            @click="removeItem(index)"
            :disabled="item.extracting"
          >
            <CloseOutlined />
          </a-button>
        </div>
      </div>
    </div>

    <!-- 预览模态框 -->
    <a-modal
      v-model:open="previewVisible"
      :title="previewTitle"
      :footer="null"
      :width="modalWidth"
      :centered="true"
      class="preview-modal"
      @cancel="closePreview"
    >
      <div class="preview-modal-content">
        <MdPreview
          v-if="previewVisible && previewContent"
          editorId="attachment-preview-editor"
          :modelValue="previewContent"
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
          <a-button type="primary" @click="closePreview">关闭</a-button>
        </div>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { 
  CloseOutlined, 
  FileOutlined, 
  LoadingOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined,
  EyeOutlined,
  FileSearchOutlined
} from '@ant-design/icons-vue';
import { MdPreview } from 'md-editor-v3';
import 'md-editor-v3/lib/preview.css';

const props = defineProps({
  attachments: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['remove', 'clear', 'showVisualization', 'previewContent']);

// 预览模态框状态
const previewVisible = ref(false);
const previewTitle = ref('');
const previewContent = ref('');

// 响应式模态框宽度
const modalWidth = computed(() => {
  if (typeof window === 'undefined') return 900;
  const width = window.innerWidth;
  if (width < 768) return '95%';
  if (width < 1024) return 800;
  return 900;
});

const removeItem = (index) => {
  emit('remove', index);
};

const clearAll = () => {
  emit('clear');
};

const showVisualization = (visualizationData) => {
  emit('showVisualization', visualizationData);
};

const openPreview = (item) => {
  previewTitle.value = `预览：${item.name}`;
  previewContent.value = item.extractedText || '';
  previewVisible.value = true;
  emit('previewContent', item);
};

const closePreview = () => {
  previewVisible.value = false;
  // 延迟清空内容，避免关闭动画时内容闪烁
  setTimeout(() => {
    previewTitle.value = '';
    previewContent.value = '';
  }, 300);
};

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};
</script>

<style lang="less" scoped>
.attachment-preview {
  width: 100%;
  padding: 12px;
  background: var(--gray-20);
  border-radius: 8px;
  margin-bottom: 8px;

  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;

    .preview-title {
      font-size: 13px;
      color: var(--gray-700);
      font-weight: 500;
    }

    .ant-btn-link {
      padding: 0;
      height: auto;
      font-size: 12px;
      color: var(--gray-600);

      &:hover {
        color: var(--main-color);
      }
    }
  }

  .preview-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .preview-item {
    position: relative;
    border-radius: 6px;
    overflow: hidden;
    background: white;
    border: 1px solid var(--gray-200);

    &.is-image {
      width: 100px;
      height: 100px;
      flex-shrink: 0;
    }

    &:not(.is-image) {
      width: 100%;
      flex-basis: 100%;
    }
  }

  .image-wrapper {
    position: relative;
    width: 100%;
    height: 100%;
    cursor: pointer;

    .preview-image {
      width: 100%;
      height: 100%;
      
      :deep(img) {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }

    .image-overlay {
      position: absolute;
      top: 0;
      right: 0;
      left: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0);
      display: flex;
      align-items: flex-start;
      justify-content: flex-end;
      padding: 4px;
      opacity: 0;
      transition: all 0.2s ease;

      .remove-btn {
        background: rgba(0, 0, 0, 0.6);
        color: white;
        border-radius: 4px;
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;

        &:hover {
          background: rgba(0, 0, 0, 0.8);
        }
      }
    }

    &:hover .image-overlay {
      opacity: 1;
      background: rgba(0, 0, 0, 0.1);
    }
  }

  .file-wrapper {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px;
    transition: all 0.3s;

    &.is-extracting {
      opacity: 0.7;
      
      .file-icon {
        color: var(--main-color);
      }
    }

    &.has-error {
      .file-icon {
        background: #fff2f0;
        color: #ff4d4f;
      }
    }

    .file-icon {
      flex-shrink: 0;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--gray-100);
      border-radius: 4px;
      font-size: 16px;
      color: var(--gray-600);
      transition: all 0.3s;
    }

    .file-info {
      flex: 1;
      min-width: 0;

      .file-name {
        font-size: 12px;
        color: var(--gray-900);
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .file-status {
        margin-top: 2px;
        display: inline-flex;
        align-items: center;
        gap: 8px;

        .status-text {
          font-size: 11px;
          display: inline-flex;
          align-items: center;
          gap: 4px;
          flex-shrink: 0;
          
          &:not(.error):not(.success) {
            color: var(--gray-500);
          }

          &.error {
            color: #ff4d4f;
          }

          &.success {
            color: #52c41a;
          }
        }
        
        .preview-btn,
        .viz-btn {
          padding: 0 4px;
          height: auto;
          font-size: 11px;
          flex-shrink: 0;
        }

        .file-size {
          font-size: 11px;
          color: var(--gray-500);
        }
      }
    }

    .remove-btn {
      flex-shrink: 0;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      color: var(--gray-500);

      &:hover {
        color: var(--gray-900);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }
  }
}

// 预览模态框样式
:deep(.preview-modal) {
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

.preview-modal-content {
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
  .preview-modal-content {
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

