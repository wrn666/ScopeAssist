<template>
  <div class="knowledge-base-result">
    <div class="kb-header">
      <h4><FileTextOutlined /> 知识库检索结果</h4>
      <div class="result-summary">
        找到 {{ data.length }} 个相关文档片段，来自 {{ fileGroups.length }} 个文件
      </div>
    </div>

    <div class="kb-results">
      <div
        v-for="fileGroup in fileGroups"
        :key="fileGroup.filename"
        class="file-group"
      >
        <!-- 文件级别的头部 -->
        <div
          class="file-header"
          :class="{ 'expanded': expandedFiles.has(fileGroup.filename) }"
          @click="toggleFile(fileGroup.filename)"
        >
          <div class="file-info">
            <FileOutlined />
            <span class="file-name">{{ fileGroup.filename }}</span>
            <span class="chunk-count">{{ fileGroup.chunks.length }} chunks</span>
          </div>
          <div class="expand-icon">
            <DownOutlined :class="{ 'rotated': expandedFiles.has(fileGroup.filename) }" />
          </div>
        </div>

        <!-- 展开的chunks列表 -->
        <div
          v-if="expandedFiles.has(fileGroup.filename)"
          class="chunks-container"
        >
          <!-- 可视化图片展示 -->
          <div v-if="fileGroup.hasVisualization" class="visualization-section">
            <div class="visualization-header">
              <span class="visualization-title">相关页面可视化</span>
              <span v-if="fileGroup.visualization" class="page-count">{{ fileGroup.visualization.total_pages }} 页</span>
            </div>
            
            <!-- 加载中状态 -->
            <div v-if="!fileGroup.visualization" class="viz-loading">
              <span>加载可视化数据中...</span>
            </div>
            
            <!-- 可视化图片 -->
            <div v-else class="visualization-images">
              <div 
                v-for="page in fileGroup.visualization.annotated_pages" 
                :key="page.page_number"
                class="viz-page-item"
                @click="showVisualization(fileGroup.visualization, page.page_number)"
              >
                <img 
                  :src="`data:image/png;base64,${page.image}`" 
                  :alt="`第 ${page.page_number} 页`"
                  class="viz-thumbnail"
                />
                <span class="viz-page-number">P{{ page.page_number }}</span>
              </div>
            </div>
          </div>

          <div
            v-for="(chunk, index) in fileGroup.chunks"
            :key="chunk.id"
            class="chunk-item"
            :class="{ 'high-relevance': chunk.score > 0.5 }"
            @click="showChunkDetail(chunk, index + 1)"
          >
            <div class="chunk-summary">
              <span class="chunk-index">#{{ index + 1 }}</span>
              <div class="chunk-scores">
                <span class="score-item">相似度 {{ (chunk.score * 100).toFixed(0) }}%</span>
                <span v-if="chunk.rerank_score" class="score-item">重排序 {{ (chunk.rerank_score * 100).toFixed(0) }}%</span>
              </div>
              <span class="chunk-preview">{{ getPreviewText(chunk.content) }}</span>
              <EyeOutlined class="view-icon" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="data.length === 0" class="no-results">
      <p>未找到相关知识库内容</p>
    </div>

    <!-- 弹窗展示chunk详细信息 -->
    <a-modal
      v-model:open="modalVisible"
      :title="`文档片段 #${selectedChunk?.index} - ${selectedChunk?.data?.metadata?.source}`"
      width="800px"
      :footer="null"
      class="chunk-detail-modal"
    >
      <div v-if="selectedChunk" class="chunk-detail">
        <div class="detail-header">
          <div class="detail-scores">
            <div class="score-card">
              <div class="score-label">相似度分数</div>
              <div class="score-value-large">{{ (selectedChunk.data.score * 100).toFixed(1) }}%</div>
              <a-progress
                :percent="getPercent(selectedChunk.data.score)"
                :stroke-color="getScoreColor(selectedChunk.data.score)"
                :show-info="false"
                stroke-width="6"
              />
            </div>
            <div v-if="selectedChunk.data.rerank_score" class="score-card">
              <div class="score-label">重排序分数</div>
              <div class="score-value-large">{{ (selectedChunk.data.rerank_score * 100).toFixed(1) }}%</div>
              <a-progress
                :percent="getPercent(selectedChunk.data.rerank_score)"
                :stroke-color="getScoreColor(selectedChunk.data.rerank_score)"
                :show-info="false"
                stroke-width="6"
              />
            </div>
          </div>
          <div class="detail-meta">
            <span class="meta-item"><DatabaseOutlined /> ID: {{ selectedChunk.data.metadata.chunk_id || selectedChunk.data.metadata.file_id }}</span>
          </div>
        </div>

        <div class="detail-content">
          <h5>文档内容</h5>
          <div class="content-text">{{ selectedChunk.data.content }}</div>
        </div>
      </div>
    </a-modal>

    <!-- 可视化详情弹窗 -->
    <a-modal
      v-model:open="vizModalVisible"
      :title="`${selectedVisualization?.data?.filename} - 第 ${selectedVisualization?.currentPage} 页可视化`"
      width="900px"
      :footer="null"
      class="viz-detail-modal"
    >
      <div v-if="selectedVisualization" class="viz-detail">
        <div class="viz-image-container">
          <img 
            :src="`data:image/png;base64,${selectedVisualization.data.annotated_pages.find(p => p.page_number === selectedVisualization.currentPage)?.image}`"
            :alt="`第 ${selectedVisualization.currentPage} 页`"
            class="viz-full-image"
          />
        </div>
        <div class="viz-info">
          <div class="viz-meta">
            <span>共 {{ selectedVisualization.data.total_pages }} 页</span>
            <span>生成时间: {{ selectedVisualization.data.created_at }}</span>
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { FileTextOutlined, FileOutlined, DownOutlined, EyeOutlined, DatabaseOutlined } from '@ant-design/icons-vue'
import { apiGet } from '@/apis/base'

const props = defineProps({
  data: {
    type: Array,
    required: true
  }
})

// 管理展开状态
const expandedFiles = ref(new Set())

// 弹窗状态
const modalVisible = ref(false)
const selectedChunk = ref(null)

// 可视化弹窗状态
const vizModalVisible = ref(false)
const selectedVisualization = ref(null)

// 用于存储可视化数据的响应式对象
const visualizationData = ref({})

// 按文件名聚合数据
const fileGroups = computed(() => {
  const groups = new Map()

  props.data.forEach(item => {
    const filename = item.metadata.source
    if (!groups.has(filename)) {
      groups.set(filename, {
        filename,
        chunks: [],
        hasVisualization: false,  // 是否有可视化数据
        fileId: null,  // 文件ID
        dbId: null,  // 数据库ID
      })
    }
    const group = groups.get(filename)
    group.chunks.push(item)
    
    // 如果该chunk有可视化标记，保存文件ID和数据库ID
    if (item.metadata.has_visualization && !group.hasVisualization) {
      group.hasVisualization = true
      group.fileId = item.metadata.file_id
      // 从工具元数据中获取数据库ID
      group.dbId = item.metadata.database_id || null
    }
  })

  // 转换为数组并按文件名排序，并附加可视化数据
  return Array.from(groups.values()).map(group => ({
    ...group,
    visualization: visualizationData.value[group.fileId] || null
  })).sort((a, b) => a.filename.localeCompare(b.filename))
})

// 切换文件展开/折叠状态
const toggleFile = async (filename) => {
  if (expandedFiles.value.has(filename)) {
    expandedFiles.value.delete(filename)
  } else {
    expandedFiles.value.add(filename)
    
    // 展开时，如果有可视化数据但未加载，则加载
    const fileGroup = fileGroups.value.find(g => g.filename === filename)
    if (fileGroup && fileGroup.hasVisualization && !fileGroup.visualization && fileGroup.dbId && fileGroup.fileId) {
      console.log('加载可视化数据:', { dbId: fileGroup.dbId, fileId: fileGroup.fileId })
      await loadVisualization(fileGroup)
    } else if (fileGroup) {
      console.log('可视化状态:', {
        hasVisualization: fileGroup.hasVisualization,
        hasData: !!fileGroup.visualization,
        dbId: fileGroup.dbId,
        fileId: fileGroup.fileId
      })
    }
  }
}

// 加载可视化数据
const loadVisualization = async (fileGroup) => {
  try {
    const url = `/api/knowledge/databases/${fileGroup.dbId}/documents/${fileGroup.fileId}/visualization`
    console.log('请求可视化数据:', url)
    
    const result = await apiGet(url)
    console.log('响应数据:', result)
    
    if (result.success && result.data) {
      // 更新响应式数据
      visualizationData.value[fileGroup.fileId] = result.data
      console.log('可视化数据加载成功:', fileGroup.fileId)
    } else {
      console.warn('未找到可视化数据:', result)
    }
  } catch (error) {
    console.error('加载可视化数据失败:', error)
  }
}

// 显示chunk详细信息
const showChunkDetail = (chunk, index) => {
  selectedChunk.value = {
    data: chunk,
    index: index
  }
  modalVisible.value = true
}

// 显示可视化详情
const showVisualization = (visualization, pageNumber) => {
  selectedVisualization.value = {
    data: visualization,
    currentPage: pageNumber
  }
  vizModalVisible.value = true
}

// 获取预览文本
const getPreviewText = (text) => {
  if (text.length <= 100) return text
  return text.substring(0, 100) + '...'
}

const getPercent = (score) => {
  if (score <= 1) {
    return Math.round(score * 100)
  }
  return Math.min(Math.round(score * 100), 100)
}

const getScoreColor = (score) => {
  if (score >= 0.7) return '#52c41a'  // 绿色 - 高相关性
  if (score >= 0.5) return '#faad14'  // 橙色 - 中等相关性
  return '#ff4d4f'  // 红色 - 低相关性
}
</script>

<style lang="less" scoped>
.knowledge-base-result {
  background: var(--gray-0);
  border-radius: 8px;
  // border: 1px solid var(--gray-200);

  .kb-header {
    padding: 12px 16px;
    // border-bottom: 1px solid var(--gray-200);
    background: var(--gray-25);

    h4 {
      margin: 0 0 4px 0;
      color: var(--gray-800);
      font-size: 14px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 6px;

      .anticon {
        color: var(--main-color);
        font-size: 13px;
      }
    }

    .result-summary {
      font-size: 12px;
      color: var(--gray-500);
    }
  }

  .kb-results {
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .file-group {
    border: 1px solid var(--gray-150);
    border-radius: 8px;
    background: var(--gray-0);
    overflow: hidden;

    .file-header {
      padding: 8px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      transition: all 0.2s ease;
      background: var(--gray-10);

      &:hover {
        background: var(--gray-25);
      }

      &.expanded {
        background: var(--gray-25);
        border-bottom: 1px solid var(--gray-100);
      }

      .file-info {
        display: flex;
        align-items: center;
        gap: 10px;
        flex: 1;
        min-width: 0;

        .anticon {
          color: var(--gray-500);
          font-size: 13px;
        }

        .file-name {
          font-size: 13px;
          font-weight: 500;
          color: var(--gray-700);
          flex: 1;
          min-width: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .chunk-count {
          font-size: 11px;
          color: var(--gray-500);
          white-space: nowrap;
          margin-right: 4px;
        }
      }

      .expand-icon {
        color: var(--gray-400);
        transition: transform 0.2s ease;
        font-size: 12px;

        .rotated {
          transform: rotate(180deg);
        }
      }
    }

    .chunks-container {
      background: var(--gray-0);
    }

    .chunk-item {
      padding: 10px 14px;
      border-bottom: 1px solid var(--gray-100);
      cursor: pointer;
      transition: all 0.2s ease;

      &:last-child {
        border-bottom: none;
      }

      &.high-relevance {
        background: var(--main-5);
      }

      &:hover {
        background: var(--gray-25);

        .view-icon {
          opacity: 1;
        }
      }

      .chunk-summary {
        display: flex;
        align-items: center;
        gap: 10px;

        .chunk-index {
          color: var(--gray-500);
          font-size: 11px;
          font-weight: 500;
          min-width: 20px;
          text-align: center;
          background: var(--gray-25);
          padding: 1px 4px;
          border-radius: 4px;
        }

        .chunk-scores {
          display: flex;
          gap: 6px;

          .score-item {
            font-size: 11px;
            color: var(--gray-600);
            background: var(--gray-25);
            padding: 1px 5px;
            border-radius: 4px;
            border: 1px solid var(--gray-100);
            white-space: nowrap;
          }
        }

        .chunk-preview {
          flex: 1;
          font-size: 12px;
          color: var(--gray-600);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          min-width: 0;
        }

        .view-icon {
          color: var(--gray-400);
          font-size: 12px;
          opacity: 0.5;
          transition: opacity 0.2s ease;
        }
      }
    }
  }

  .no-results {
    text-align: center;
    color: var(--gray-500);
    padding: 20px;
    font-size: 12px;
  }

  .visualization-section {
    padding: 12px;
    background: var(--gray-10);
    border-bottom: 1px solid var(--gray-100);

    .visualization-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;

      .visualization-title {
        font-size: 13px;
        font-weight: 500;
        color: var(--gray-700);
      }

      .page-count {
        font-size: 11px;
        color: var(--gray-500);
        background: var(--gray-25);
        padding: 2px 8px;
        border-radius: 4px;
      }
    }

    .viz-loading {
      padding: 20px;
      text-align: center;
      color: var(--gray-500);
      font-size: 13px;
      
      span::before {
        content: '⏳ ';
      }
    }

    .visualization-images {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 4px;

      .viz-page-item {
        flex-shrink: 0;
        cursor: pointer;
        border-radius: 6px;
        overflow: hidden;
        border: 2px solid var(--gray-150);
        transition: all 0.2s ease;
        position: relative;

        &:hover {
          border-color: var(--main-color);
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }

        .viz-thumbnail {
          width: 120px;
          height: 160px;
          object-fit: cover;
          display: block;
        }

        .viz-page-number {
          position: absolute;
          top: 4px;
          right: 4px;
          background: rgba(0, 0, 0, 0.6);
          color: white;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: 500;
        }
      }
    }
  }
}

:deep(.chunk-detail-modal) {
  .ant-modal-header {
    border-bottom: 1px solid var(--gray-200);
    margin-bottom: 0;
  }

  .ant-modal-title {
    color: var(--main-color);
    font-weight: 500;
  }
}

.chunk-detail {
  .detail-header {
    margin-bottom: 16px;

    .detail-scores {
      display: flex;
      gap: 16px;
      margin-bottom: 12px;

      .score-card {
        flex: 1;
        padding: 12px 14px;
        background: var(--gray-25);
        border-radius: 8px;
        border: 1px solid var(--gray-150);

        .score-label {
          font-size: 12px;
          color: var(--gray-500);
          margin-bottom: 6px;
          font-weight: 500;
        }

        .score-value-large {
          font-size: 18px;
          font-weight: 600;
          color: var(--gray-800);
          margin-bottom: 8px;
        }
      }
    }

    .detail-meta {
      display: flex;
      gap: 12px;

      .meta-item {
        font-size: 11px;
        color: var(--gray-400);
        display: flex;
        align-items: center;
        gap: 4px;

        .anticon {
          color: var(--gray-500);
        }
      }
    }
  }

  .detail-content {
    h5 {
      margin: 0 0 8px 0;
      color: var(--gray-800);
      font-size: 14px;
      font-weight: 500;
    }

    .content-text {
      font-size: 13px;
      line-height: 1.6;
      color: var(--gray-700);
      white-space: pre-wrap;
      word-break: break-word;
      background: var(--gray-25);
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--gray-150);
      max-height: 400px;
      overflow-y: auto;
    }
  }
}

:deep(.viz-detail-modal) {
  .ant-modal-header {
    border-bottom: 1px solid var(--gray-200);
    margin-bottom: 0;
  }

  .ant-modal-title {
    color: var(--main-color);
    font-weight: 500;
  }
}

.viz-detail {
  .viz-image-container {
    margin-bottom: 16px;
    display: flex;
    justify-content: center;
    background: var(--gray-25);
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--gray-150);

    .viz-full-image {
      max-width: 100%;
      height: auto;
      border-radius: 4px;
    }
  }

  .viz-info {
    .viz-meta {
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: var(--gray-600);
      padding: 12px;
      background: var(--gray-25);
      border-radius: 8px;

      span {
        display: flex;
        align-items: center;
        gap: 4px;
      }
    }
  }
}
</style>