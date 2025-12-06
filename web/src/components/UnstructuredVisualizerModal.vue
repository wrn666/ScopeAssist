<template>
  <a-modal
    v-model:open="visible"
    title="Unstructured 文档可视化"
    width="1400px"
    :footer="null"
    @cancel="handleCancel"
    :bodyStyle="{ height: '85vh', padding: '0' }"
  >
    <div class="visualizer-container">
      <!-- 上传区域 -->
      <div v-if="!visualizationData" class="upload-section">
        <a-upload-dragger
          :file-list="[]"
          :before-upload="handleFileUpload"
          accept=".pdf"
          :show-upload-list="false"
        >
          <p class="ant-upload-drag-icon">
            <FileOutlined />
          </p>
          <p class="ant-upload-text">点击或拖拽 PDF 文件到这里</p>
          <p class="ant-upload-hint">
            支持 PDF 文件，系统会自动识别文档结构并标注
          </p>
        </a-upload-dragger>
        
        <div v-if="processing" class="processing-status">
          <a-spin />
          <p>正在处理文档，请稍候...</p>
        </div>
      </div>

      <!-- 可视化区域 -->
      <div v-else class="visualization-section">
        <!-- 工具栏 -->
        <div class="toolbar">
          <div class="page-controls">
            <a-button @click="prevPage" :disabled="currentPage <= 1" size="small">
              <LeftOutlined /> 上一页
            </a-button>
            <span class="page-info">
              第 {{ currentPage }} / {{ totalPages }} 页
            </span>
            <a-button @click="nextPage" :disabled="currentPage >= totalPages" size="small">
              下一页 <RightOutlined />
            </a-button>
          </div>
          
          <a-button @click="resetVisualization" size="small">
            <ReloadOutlined /> 重新上传
          </a-button>
        </div>

        <!-- 统一滚动容器 -->
        <div class="unified-scroll-container">
          <!-- 标注图片容器 -->
          <div class="image-container">
            <img
              v-if="currentPageImage" 
              :src="`data:image/png;base64,${currentPageImage}`"
              alt="标注页面"
              class="annotated-image"
            />
            <div v-else class="loading-page">
              <a-spin />
              <p>加载中...</p>
            </div>
          </div>

          <!-- 当前页内容列表 -->
          <div class="content-list">
            <div class="content-header">当前页识别内容 ({{ currentPageElements.length }} 个元素)</div>
            <div class="content-items">
              <div 
                v-for="(element, index) in currentPageElements" 
                :key="index"
                class="content-item"
              >
                <div class="element-header">
                  <span class="element-category" :style="{ color: getCategoryColor(element.category) }">
                    {{ element.category || 'Text' }}
                  </span>
                  <span class="element-index">#{{ index + 1 }}</span>
                </div>
                <div class="element-text">{{ element.text || '(无文本内容)' }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import { FileOutlined, LeftOutlined, RightOutlined, ReloadOutlined } from '@ant-design/icons-vue';
import { agentApi } from '@/apis/agent_api';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  preLoadedData: {
    type: Object,
    default: null
  }
});

const emit = defineEmits(['update:visible']);

const visible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
});

const processing = ref(false);
const visualizationData = ref(null);
const currentPage = ref(1);
const totalPages = ref(0);

// 颜色映射
const categoryColors = {
  'Title': '#da70d6',      // orchid
  'Image': '#228b22',      // forestgreen
  'Table': '#ff6347',      // tomato
  'Text': '#00bfff',       // deepskyblue
  'Header': '#9370db',     // mediumpurple
  'Subheader': '#ba55d3',  // mediumorchid
};

// 获取类别颜色
const getCategoryColor = (category) => {
  return categoryColors[category] || categoryColors['Text'];
};

// 当前页的图片
const currentPageImage = computed(() => {
  if (!visualizationData.value || !visualizationData.value.annotated_pages) {
    return null;
  }
  const page = visualizationData.value.annotated_pages.find(
    p => p.page_number === currentPage.value
  );
  return page ? page.image : null;
});

// 当前页的元素列表
const currentPageElements = computed(() => {
  if (!visualizationData.value || !visualizationData.value.annotated_pages) {
    return [];
  }
  const page = visualizationData.value.annotated_pages.find(
    p => p.page_number === currentPage.value
  );
  return page ? page.elements : [];
});

// 文件上传处理
const handleFileUpload = async (file) => {
  processing.value = true;
  
  try {
    const result = await agentApi.visualizeUnstructured(file);
    
    if (result.success) {
      visualizationData.value = result;
      totalPages.value = result.total_pages || 0;
      currentPage.value = 1;
      message.success('文档处理成功');
    } else {
      message.error(result.message || '处理失败');
    }
  } catch (error) {
    console.error('处理文档失败:', error);
    message.error('处理文档失败: ' + error.message);
  } finally {
    processing.value = false;
  }
  
  return false; // 阻止自动上传
};

// 翻页
const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
};

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
};

// 重置
const resetVisualization = () => {
  visualizationData.value = null;
  currentPage.value = 1;
  totalPages.value = 0;
};

// 关闭弹窗
const handleCancel = () => {
  resetVisualization();
  visible.value = false;
};

// 监听预加载数据
watch(() => props.preLoadedData, (newData) => {
  if (newData && props.visible) {
    visualizationData.value = newData;
    totalPages.value = newData.total_pages || 0;
    currentPage.value = 1;
  }
}, { immediate: true });

// 监听弹窗关闭
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    resetVisualization();
  }
});
</script>

<style scoped>
.visualizer-container {
  min-height: 500px;
}

.upload-section {
  padding: 20px;
}

.processing-status {
  text-align: center;
  padding: 40px;
}

.processing-status p {
  margin-top: 16px;
  color: #666;
}

.visualization-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(85vh - 120px); /* 减去工具栏高度 */
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f5f5;
  border-radius: 4px;
}

.page-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-info {
  font-size: 14px;
  color: #666;
  min-width: 120px;
  text-align: center;
}

/* 统一滚动容器 */
.unified-scroll-container {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.image-container {
  width: 100%;
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  flex-shrink: 0; /* 防止图片容器被压缩 */
}

.annotated-image {
  max-width: 100%;
  height: auto;
  display: block;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.loading-page {
  text-align: center;
  padding: 60px;
}

.loading-page p {
  margin-top: 16px;
  color: #666;
}

.content-list {
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  flex-shrink: 0; /* 防止内容列表被压缩 */
}

.content-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  font-weight: 600;
  font-size: 14px;
}

.content-items {
  padding: 8px;
}

.content-item {
  padding: 12px;
  margin-bottom: 8px;
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  transition: all 0.2s;
}

.content-item:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
}

.element-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.element-category {
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
}

.element-index {
  font-size: 12px;
  color: #999;
}

.element-text {
  font-size: 13px;
  color: #333;
  line-height: 1.6;
  max-height: 100px;
  overflow: auto;
  word-break: break-word;
}
</style>