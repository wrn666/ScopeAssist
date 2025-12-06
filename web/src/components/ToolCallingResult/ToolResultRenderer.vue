<template>
  <div class="tool-result-renderer">
    <!-- 网页搜索结果 -->
    <WebSearchResult
      v-if="isWebSearchResult"
      :data="parsedData"
    />

    <!-- 知识库检索结果 -->
    <KnowledgeBaseResult
      v-else-if="isKnowledgeBaseResult"
      :data="parsedData"
    />

    <!-- 图片结果 -->
    <div v-else-if="isImageResult" class="image-result">
      <img :src="parsedData" />
    </div>

    <!-- 默认的原始数据展示 -->
    <div v-else class="default-result">
      <!-- <div class="default-header">
        <h4><ToolOutlined /> {{ toolName }} 执行结果</h4>
      </div> -->
      <div class="default-content">
        <pre>{{ formatData(parsedData) }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import WebSearchResult from './WebSearchResult.vue'
import KnowledgeBaseResult from './KnowledgeBaseResult.vue'
import { useAgentStore } from '@/stores/agent';

const agentStore = useAgentStore()

const props = defineProps({
  toolName: {
    type: String,
    required: true
  },
  resultContent: {
    type: [String, Object, Array, Number],
    required: true
  }
})

const tool = computed(() => {
  return agentStore?.availableTools?.[props.toolName] || null
})


// 解析数据
const parsedData = computed(() => {
  if (typeof props.resultContent === 'string') {
    try {
      return JSON.parse(props.resultContent)
    } catch {
      return props.resultContent
    }
  }
  return props.resultContent
})

// 判断是否为网页搜索结果
const isWebSearchResult = computed(() => {
  const toolNameLower = props.toolName.toLowerCase()
  const isWebSearchTool = toolNameLower.includes('search') ||
                         toolNameLower.includes('tavily') ||
                         toolNameLower.includes('web')

  if (!isWebSearchTool) return false

  const data = parsedData.value
  return data &&
         typeof data === 'object' &&
         'results' in data &&
         Array.isArray(data.results) &&
         'query' in data
})

// 判断是否为知识库检索结果
const isKnowledgeBaseResult = computed(() => {
  // 首先检查工具的 metadata
  const currentTool = tool.value
  if (currentTool && currentTool.metadata) {
    const metadata = currentTool.metadata
    const hasKnowledgebaseTag = metadata.tag && metadata.tag.includes('knowledgebase')
    const isNotLightrag = metadata.kb_type !== 'lightrag'

    if (hasKnowledgebaseTag && isNotLightrag) {
      const data = parsedData.value
      return Array.isArray(data) &&
             data.length > 0 &&
             data.every(item =>
               item &&
               typeof item === 'object' &&
               'content' in item &&
               'score' in item &&
               'metadata' in item
             )
    }
  }

  return false
})

const isImageResult = computed(() => {
  // 包含 chart 且返回值是url
  const data = parsedData.value
  const toolNameLower = props.toolName.toLowerCase()
  const isImageTool = toolNameLower.includes('chart')

  if (!isImageTool) return false

  return data && typeof data === 'string' && data.startsWith('http')
})

// 格式化数据用于默认展示
const formatData = (data) => {
  if (typeof data === 'object') {
    return JSON.stringify(data, null, 2)
  }
  return String(data)
}

</script>

<style lang="less" scoped>
.tool-result-renderer {
  width: 100%;
  height: 100%;

  .default-result {
    background: var(--gray-0);
    border-radius: 8px;

    .default-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--gray-100);
      background: var(--gray-25);

      h4 {
        margin: 0;
        color: var(--main-color);
        font-size: 14px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
      }
    }

    .default-content {
      background: var(--gray-0);
      padding: 12px;

      pre {
        margin: 0;
        font-size: 12px;
        line-height: 1.4;
        color: var(--gray-700);
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 300px;
        overflow-y: auto;
        background: var(--gray-50);
        padding: 10px;
        border-radius: 4px;
        // border-left: 2px solid var(--main-color);
      }
    }
  }

  .image-result {
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
}
</style>