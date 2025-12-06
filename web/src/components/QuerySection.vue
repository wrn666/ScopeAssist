<template>
  <div class="query-section" :class="{ collapsed: !visible }" :style="style">
    <div class="section-header">
      <h3 class="section-title">检索测试</h3>
      <div class="panel-actions">
        <a-button
          type="text"
          size="small"
          @click="toggleVisible"
          title="折叠/展开"
        >
          <component :is="visible ? UpOutlined : DownOutlined" />
        </a-button>
      </div>
    </div>

    <div class="query-content content" v-show="visible">
      <div class="query-layout">
        <!-- 左侧：查询参数面板 -->
        <div class="query-params-panel">
          <div class="params-header">
            <h4 class="params-title">查询参数</h4>
          </div>
          <div class="params-content">
            <div v-if="loading" class="params-loading">
              <a-spin size="small" />
            </div>
            <div v-else class="params-list">
              <div v-for="param in queryParams" :key="param.key" class="param-item">
                <label class="param-label">{{ param.label }}</label>
                <a-select
                  v-if="param.type === 'select'"
                  v-model:value="meta[param.key]"
                  size="small"
                  style="width: 100%;"
                >
                  <a-select-option
                    v-for="option in param.options"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </a-select-option>
                </a-select>
                <a-switch
                  v-else-if="param.type === 'boolean'"
                  v-model:checked="meta[param.key]"
                  size="small"
                />
                <a-input-number
                  v-else-if="param.type === 'number'"
                  v-model:value="meta[param.key]"
                  size="small"
                  style="width: 100%;"
                  :min="param.min || 0"
                  :max="param.max || 100"
                />
              </div>
              <div v-if="!loading && queryParams.length === 0" class="params-empty">
                <p>暂无查询参数</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：输入框和结果 -->
        <div class="query-right-panel">
          <!-- 上方：检索测试输入框 -->
          <div class="query-input-container">
            <a-textarea
              v-model:value="queryText"
              placeholder="输入查询内容"
              :auto-size="{ minRows: 3, maxRows: 6 }"
              class="compact-query-textarea"
            />
            <div class="query-actions-row">
              <a-button
                @click="onQuery"
                :loading="searchLoading"
                type="primary"
                class="search-button"
              >
                <template #icon>
                  <SearchOutlined />
                </template>
                搜索
              </a-button>
              <div class="query-examples-compact">
                <span class="examples-label">示例：</span>
                <div class="examples-container">
                  <transition name="fade" mode="out-in">
                    <a-button
                      type="text"
                      :key="currentExampleIndex"
                      @click="useQueryExample(queryExamples[currentExampleIndex])"
                      size="small"
                      class="example-btn"
                    >
                      {{ queryExamples[currentExampleIndex] }}
                    </a-button>
                  </transition>
                </div>
              </div>
            </div>
          </div>

          <!-- 下方：检索测试结果 -->
          <div class="query-results-container">
            <div class="results-header">
              <h4 class="results-title">检索结果</h4>
              <a-button
                v-if="queryResult"
                type="text"
                size="small"
                @click="handleCopyResult"
                title="复制结果"
              >
                <template #icon>
                  <CopyOutlined />
                </template>
                复制
              </a-button>
            </div>
            <div class="query-results">
              <transition name="fade" mode="out-in">
                <div v-if="!queryResult && !searchLoading" key="empty" class="results-empty">
                  <p>请输入查询内容并点击搜索</p>
                </div>
                <div v-else-if="searchLoading" key="loading" class="results-loading">
                  <a-spin size="large" />
                  <p>正在检索...</p>
                </div>
                <div v-else key="content" class="results-content">
                  <pre v-if="typeof queryResult === 'object' && queryResult !== null">{{ formatResult(queryResult) }}</pre>
                  <div v-else-if="queryResult">{{ queryResult }}</div>
                  <div v-else class="results-empty">
                    <p>暂无结果</p>
                  </div>
                </div>
              </transition>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useDatabaseStore } from '@/stores/database';
import { message } from 'ant-design-vue';
import { queryApi } from '@/apis/knowledge_api';
import {
  SearchOutlined,
  UpOutlined,
  DownOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue';

const store = useDatabaseStore();

const props = defineProps({
  visible: {
    type: Boolean,
    default: true
  },
  style: {
    type: Object,
    default: () => ({})
  },
});

const emit = defineEmits(['toggleVisible']);

const loading = computed(() => store.state.queryParamsLoading);
const searchLoading = computed(() => store.state.searchLoading);
const queryParams = computed(() => store.queryParams);
const meta = computed({
  get: () => store.meta,
  set: (value) => Object.assign(store.meta, value)
});
const queryResult = ref('');

// 查询测试
const queryText = ref('');

// 添加更多示例查询
const queryExamples = ref([
  '孕妇应该避免吃哪些水果？',
  '荔枝应该怎么清洗？',
  '如何判断西瓜是否成熟？',
  '苹果有哪些营养价值？',
  '什么季节最适合吃梨？',
  '如何保存草莓以延长保质期？',
  '香蕉变黑后还能吃吗？',
  '橙子皮可以用来做什么？'
]);

// 当前示例索引
const currentExampleIndex = ref(0);

// 示例轮播相关
let exampleCarouselInterval = null;

const toggleVisible = () => {
  emit('toggleVisible');
};

const onQuery = async () => {
  if (!queryText.value.trim()) {
    message.error('请输入查询内容');
    return;
  }

  store.state.searchLoading = true;

  // 确保只传递当前知识库类型支持的参数
  const supportedParamKeys = new Set(queryParams.value.map(param => param.key));
  const queryMeta = {};

  // 遍历 meta 中的参数，只保留当前知识库类型支持的参数
  for (const [key, value] of Object.entries(meta.value)) {
    // 跳过 db_id 参数
    if (key === 'db_id') continue;

    // 只保留当前知识库类型支持的参数
    if (supportedParamKeys.has(key)) {
      queryMeta[key] = value;
    }
  }

  try {
    const data = await queryApi.queryTest(store.database.db_id, queryText.value.trim(), queryMeta);
    queryResult.value = data;
  } catch (error) {
    console.error(error);
    message.error(error.message);
    queryResult.value = '';
  } finally {
    store.state.searchLoading = false;
  }
};

const useQueryExample = (example) => {
  queryText.value = example;
  onQuery();
};

// 格式化查询结果
const formatResult = (result) => {
  try {
    return JSON.stringify(result, null, 2);
  } catch (e) {
    return String(result);
  }
};

// 复制结果到剪贴板
const handleCopyResult = async () => {
  try {
    const text = typeof queryResult.value === 'object' && queryResult.value !== null
      ? formatResult(queryResult.value)
      : String(queryResult.value);
    await navigator.clipboard.writeText(text);
    message.success('结果已复制到剪贴板');
  } catch (error) {
    console.error('复制失败:', error);
    message.error('复制失败，请手动复制');
  }
};

const startExampleCarousel = () => {
  if (exampleCarouselInterval) return;

  exampleCarouselInterval = setInterval(() => {
    currentExampleIndex.value = (currentExampleIndex.value + 1) % queryExamples.value.length;
  }, 6000); // 每6秒切换一次
};

const stopExampleCarousel = () => {
  if (exampleCarouselInterval) {
    clearInterval(exampleCarouselInterval);
    exampleCarouselInterval = null;
  }
};

// 组件挂载时启动示例轮播
onMounted(() => {
  // 启动示例轮播
  startExampleCarousel();

  // 加载查询参数
  store.loadQueryParams();
});

// 组件卸载时停止示例轮播
onUnmounted(() => {
  // 停止示例轮播
  stopExampleCarousel();
});
</script>

<style scoped lang="less">
.query-section {
  .query-content {
    padding: 16px;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .query-layout {
    display: flex;
    gap: 16px;
    height: 100%;
    overflow: hidden;

    @media (max-width: 768px) {
      flex-direction: column;
    }
  }

  // 左侧：查询参数面板
  .query-params-panel {
    width: 280px;
    flex-shrink: 0;
    background-color: #fafafa;
    border: 1px solid #e8e8e8;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    overflow: hidden;

    @media (max-width: 768px) {
      width: 100%;
      max-height: 300px;
    }

    .params-header {
      padding: 12px 16px;
      border-bottom: 1px solid #e8e8e8;
      background-color: #fff;

      .params-title {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: #262626;
      }
    }

    .params-content {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
    }

    .params-loading {
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 40px 0;
    }

    .params-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .param-item {
      display: flex;
      flex-direction: column;
      gap: 8px;

      .param-label {
        font-size: 13px;
        font-weight: 500;
        color: #595959;
      }
    }

    .params-empty {
      text-align: center;
      padding: 40px 0;
      color: #8c8c8c;
      font-size: 13px;
    }
  }

  // 右侧：输入框和结果面板
  .query-right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
    overflow: hidden;
  }

  // 上方：检索测试输入框
  .query-input-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex-shrink: 0;

    .compact-query-textarea {
      &:focus {
        outline: none;
      }
    }

    .query-actions-row {
      display: flex;
      gap: 16px;
      align-items: center;
    }

    .search-button {
      flex-shrink: 0;
    }

    .query-examples-compact {
      display: flex;
      flex-direction: row;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }

    .examples-label {
      font-size: 12px;
      color: #8c8c8c;
      white-space: nowrap;
    }

    .examples-container {
      min-height: 24px;
      display: flex;
    }

    .example-btn {
      text-align: left;
      white-space: normal;
      height: auto;
      padding: 4px 8px;
      font-size: 12px;
    }
  }

  // 下方：检索测试结果
  .query-results-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    background-color: #fafafa;
    border: 1px solid #e8e8e8;
    border-radius: 4px;
    overflow: hidden;

    .results-header {
      padding: 12px 16px;
      border-bottom: 1px solid #e8e8e8;
      background-color: #fff;
      display: flex;
      justify-content: space-between;
      align-items: center;

      .results-title {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: #262626;
      }
    }

    .query-results {
      flex: 1;
      overflow-y: auto;
      min-height: 0;

      .results-empty {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100%;
        color: #8c8c8c;
        font-size: 13px;
      }

      .results-loading {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100%;
        gap: 12px;
        color: #8c8c8c;
        font-size: 13px;
      }

      .results-content {
        padding: 16px;
        white-space: pre-wrap;
        word-break: break-word;
        font-size: 13px;
        line-height: 1.6;
        color: #262626;

        pre {
          margin: 0;
          padding: 0;
          background: transparent;
          border: none;
          font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
          white-space: pre-wrap;
          word-break: break-word;
          max-height: 100%;
          overflow: auto;
        }
      }
    }
  }
}

// 过渡动画
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>