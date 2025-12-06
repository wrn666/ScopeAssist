<template>
<div class="database-info-container">
  <DatabaseHeader />

  <!-- Maximize Graph Modal -->
  <a-modal
    v-model:open="isGraphMaximized"
    :footer="null"
    :closable="false"
    width="100%"
    wrap-class-name="full-modal"
    :mask-closable="false"
  >
    <template #title>
      <div class="maximized-graph-header">
        <h3>知识图谱 (最大化)</h3>
        <a-button type="text" @click="toggleGraphMaximize">
          <CompressOutlined /> 退出最大化
        </a-button>
      </div>
    </template>
    <div class="maximized-graph-content">
      <div v-if="!isGraphSupported" class="graph-disabled">
        <div class="disabled-content">
          <h4>知识图谱不可用</h4>
          <p>当前知识库类型 "{{ getKbTypeLabel(database.kb_type || 'lightrag') }}" 不支持知识图谱功能。</p>
          <p>只有 LightRAG 类型的知识库支持知识图谱。</p>
        </div>
      </div>
      <KnowledgeGraphViewer
        v-else-if="isGraphMaximized"
        :initial-database-id="databaseId"
        :hide-db-selector="true"
      />
    </div>
  </a-modal>

  <FileDetailModal />

  <FileUploadModal
    v-model:visible="addFilesModalVisible"
  />

  <div class="unified-layout">
    <!-- 侧边栏 -->
    <div class="sidebar" :style="{ width: sidebarWidth + 'px' }">
      <!-- CodeHub 知识库：显示选择列表 -->
      <a-menu
        v-if="isCodeHubDatabase"
        v-model:selectedKeys="selectedMenuKeys"
        mode="inline"
        class="sidebar-menu"
        @select="handleMenuSelect"
      >
        <a-menu-item key="graph">
          <template #icon>
            <DeploymentUnitOutlined />
          </template>
          <span>知识图谱</span>
        </a-menu-item>
        <a-menu-item key="repositories">
          <template #icon>
            <FolderOutlined />
          </template>
          <span>代码仓库</span>
        </a-menu-item>
        <a-menu-item key="query">
          <template #icon>
            <SearchOutlined />
          </template>
          <span>检索测试</span>
        </a-menu-item>
      </a-menu>
      <!-- 其他知识库：显示菜单 -->
      <a-menu
        v-else
        v-model:selectedKeys="selectedMenuKeys"
        mode="inline"
        class="sidebar-menu"
        @select="handleMenuSelect"
      >
        <a-menu-item key="files">
          <template #icon>
            <FileTextOutlined />
          </template>
          <span>文件列表</span>
        </a-menu-item>
        <a-menu-item key="query">
          <template #icon>
            <SearchOutlined />
          </template>
          <span>检索测试</span>
        </a-menu-item>
      </a-menu>
    </div>

    <!-- 侧边栏拖拽手柄 -->
    <div
      class="resize-handle-left"
      ref="resizeHandleLeft"
    ></div>

    <!-- 主内容区域 -->
    <div class="main-content" :style="{ width: `calc(100% - ${sidebarWidth}px - 4px)` }">
      <!-- CodeHub 知识库：显示知识图谱、代码仓库和检索测试 -->
      <template v-if="isCodeHubDatabase">
        <!-- 知识图谱视图 -->
        <div v-if="activeView === 'graph'" class="content-view graph-view">
          <KnowledgeGraphViewer
            :initial-database-id="databaseId"
            :hide-db-selector="true"
            :hide-controls="false"
            :kb-type="'codehub'"
            :initial-limit="200"
          />
        </div>
        <!-- 代码仓库视图 -->
        <div v-if="activeView === 'repositories'" class="content-view">
          <CodeHubRepositories />
        </div>
        <!-- 检索测试视图 -->
        <div v-if="activeView === 'query'" class="content-view query-view">
          <QuerySection
            :visible="true"
          />
        </div>
      </template>
      <!-- 其他知识库：显示文件列表和检索测试 -->
      <template v-else>
        <!-- 文件列表视图 -->
        <div v-if="activeView === 'files'" class="content-view">
          <FileTable
            :right-panel-visible="false"
            @show-add-files-modal="showAddFilesModal"
          />
        </div>

        <!-- 检索测试视图 -->
        <div v-if="activeView === 'query'" class="content-view query-view">
          <QuerySection
            :visible="true"
          />
        </div>
      </template>
    </div>
  </div>
</div>
</template>

<script setup>
import { onMounted, reactive, ref, watch, onUnmounted, computed } from 'vue';
import { useRoute } from 'vue-router';
import { useDatabaseStore } from '@/stores/database';
import { getKbTypeLabel } from '@/utils/kb_utils';
import { CompressOutlined, FileTextOutlined, SearchOutlined, FolderOutlined, DeploymentUnitOutlined } from '@ant-design/icons-vue';
import KnowledgeGraphViewer from '@/components/KnowledgeGraphViewer.vue';
import DatabaseHeader from '@/components/DatabaseHeader.vue';
import FileTable from '@/components/FileTable.vue';
import FileDetailModal from '@/components/FileDetailModal.vue';
import FileUploadModal from '@/components/FileUploadModal.vue';
import QuerySection from '@/components/QuerySection.vue';
import CodeHubRepositories from '@/components/CodeHubRepositories.vue';

const route = useRoute();
const store = useDatabaseStore();

const databaseId = computed(() => store.databaseId);
const database = computed(() => store.database || {});
const state = computed(() => store.state);
const isGraphMaximized = computed({
    get: () => store.state.isGraphMaximized,
    set: (val) => store.state.isGraphMaximized = val
});

// 计算属性：是否支持知识图谱
const isGraphSupported = computed(() => {
  if (!database.value || !database.value.kb_type) return false;
  const kbType = database.value.kb_type.toLowerCase();
  return kbType === 'lightrag';
});

// 计算属性：是否是CodeHub类型知识库
const isCodeHubDatabase = computed(() => {
  if (!database.value || !database.value.kb_type) return false;
  const kbType = database.value.kb_type.toLowerCase();
  return kbType === 'codehub';
});

// 侧边栏相关
const sidebarWidth = ref(200);
const selectedMenuKeys = ref(['files']);
const activeView = ref('files');

// 监听知识库类型变化，调整侧边栏宽度和默认视图
watch(isCodeHubDatabase, (isCodeHub) => {
  if (isCodeHub) {
    sidebarWidth.value = 200;
    selectedMenuKeys.value = ['graph'];
    activeView.value = 'graph';
  } else {
    sidebarWidth.value = 200;
    selectedMenuKeys.value = ['files'];
    activeView.value = 'files';
  }
}, { immediate: true });

const handleMenuSelect = ({ key }) => {
  activeView.value = key;
  selectedMenuKeys.value = [key];
};

const isDraggingSidebar = ref(false);
const resizeHandleLeft = ref(null);

const handleSidebarMouseDown = () => {
  isDraggingSidebar.value = true;
  document.addEventListener('mousemove', handleSidebarMouseMove);
  document.addEventListener('mouseup', handleSidebarMouseUp);
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
};

const handleSidebarMouseMove = (e) => {
  if (!isDraggingSidebar.value) return;
  const container = document.querySelector('.unified-layout');
  if (!container) return;
  const containerRect = container.getBoundingClientRect();
  const newWidth = e.clientX - containerRect.left;
  sidebarWidth.value = Math.max(150, Math.min(300, newWidth));
};

const handleSidebarMouseUp = () => {
  isDraggingSidebar.value = false;
  document.removeEventListener('mousemove', handleSidebarMouseMove);
  document.removeEventListener('mouseup', handleSidebarMouseUp);
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
};

// 添加文件弹窗
const addFilesModalVisible = ref(false);

// 显示添加文件弹窗
const showAddFilesModal = () => {
  addFilesModalVisible.value = true;
};

// 切换图谱最大化状态
const toggleGraphMaximize = () => {
  isGraphMaximized.value = !isGraphMaximized.value;
};

watch(() => route.params.database_id, async (newId) => {
    store.databaseId = newId;
    store.stopAutoRefresh();
    await store.getDatabaseInfo(newId);
    store.startAutoRefresh();
  },
  { immediate: true }
);

// 组件挂载时
onMounted(() => {
  store.databaseId = route.params.database_id;
  store.getDatabaseInfo();
  store.startAutoRefresh();

  if (resizeHandleLeft.value) {
    resizeHandleLeft.value.addEventListener('mousedown', handleSidebarMouseDown);
  }
});

// 组件卸载时
onUnmounted(() => {
  store.stopAutoRefresh();
  if (resizeHandleLeft.value) {
    resizeHandleLeft.value.removeEventListener('mousedown', handleSidebarMouseDown);
  }
  document.removeEventListener('mousemove', handleSidebarMouseMove);
  document.removeEventListener('mouseup', handleSidebarMouseUp);
});

</script>

<style lang="less" scoped>
.db-main-container {
  display: flex;
  width: 100%;
}

.ant-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.auto-refresh-control {
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: 6px;

  span {
    color: var(--gray-700);
    font-weight: 500;
    font-size: 14px;
  }

  .ant-switch {
    &.ant-switch-checked {
      background-color: var(--main-color);
    }
  }
}

/* Unified Layout Styles */
.unified-layout {
  display: flex;
  height: calc(100vh - 54px);
  gap: 0;
  position: relative;
  width: 100%;

  .sidebar {
    position: relative;
    flex-shrink: 0;
    height: 100%;
    background-color: #fff;
    border-right: 1px solid var(--gray-200);
    z-index: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;

    .sidebar-menu {
      border-right: none;
      height: 100%;
      padding: 8px 0;
      overflow-y: auto;
      overflow-x: hidden;

      :deep(.ant-menu-item) {
        margin: 4px 8px;
        border-radius: 6px;
        height: 40px;
        line-height: 40px;

        &.ant-menu-item-selected {
          background-color: var(--main-10);
          color: var(--main-color);
          font-weight: 500;

          &::after {
            display: none;
          }
        }

        &:hover {
          background-color: var(--gray-50);
        }
      }

      :deep(.ant-menu-item-icon) {
        font-size: 16px;
      }
    }

    .sidebar-graph-container {
      flex: 1;
      height: 100%;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .graph-view {
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
  }

  .resize-handle-left {
    position: relative;
    width: 4px;
    height: 100%;
    cursor: col-resize;
    background-color: transparent;
    z-index: 2;
    transition: background-color 0.2s ease;
    pointer-events: auto;
    flex-shrink: 0;

    &:hover {
      background-color: var(--main-40);
    }
  }

  .main-content {
    flex: 1;
    height: 100%;
    overflow: hidden;
    transition: width 0.2s ease;
    position: relative;
    z-index: 0;
    min-width: 0;
    display: flex;
    flex-direction: column;

    .codehub-tabs {
      flex-shrink: 0;
      background: white;
      border-bottom: 1px solid var(--gray-200);
      padding: 0 16px;

      :deep(.ant-menu) {
        border-bottom: none;
      }
    }

    .content-view {
      flex: 1;
      height: 0;
      width: 100%;
      overflow: hidden;

      &.query-view {
        display: flex;
        flex-direction: column;
      }
    }
  }
}


/* Improve the resize handle visibility */
.resize-handle,
.resize-handle-horizontal {
  transition: all 0.2s ease;
  opacity: 0.6;

  &:hover {
    opacity: 1;
    background-color: var(--main-color);
  }
}

/* Responsive design for smaller screens */
@media (max-width: 768px) {
  .unified-layout {
    .sidebar {
      width: 180px !important;
    }

    .main-content {
      width: calc(100% - 180px - 4px) !important;
    }
  }
}

/* Table row selection styling */
:deep(.ant-table-tbody > tr.ant-table-row-selected > td) {
  background-color: var(--main-5);
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: var(--main-5);
}
</style>

<style lang="less">
:deep(.full-modal) {
  .ant-modal {
    max-width: 100%;
    top: 0;
    padding-bottom: 0;
    margin: 0;
    padding: 0;
  }

  .ant-modal-content {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 200px);
  }

  .ant-modal-body {
    flex: 1;
  }
}



.maximized-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h3 {
    margin: 0;
    color: var(--gray-800);
  }
}


.maximized-graph-content {
  height: calc(100vh - 300px);
  border-radius: 6px;
  overflow: hidden;
}


/* 全局样式作为备用方案 */
.ant-popover .query-params-compact {
  width: 220px;
}

.ant-popover .query-params-compact .params-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80px;
}

.ant-popover .query-params-compact .params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}

.ant-popover .query-params-compact .param-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.ant-popover .query-params-compact .param-item label {
  font-weight: 500;
  color: var(--gray-700);
  margin-right: 8px;
}


/* Improve panel transitions */
.panel-section {
  display: flex;
  flex-direction: column;
  border-radius: 4px;
  transition: all 0.3s;
  min-height: 0;

  &.collapsed {
    height: 36px;
    flex: none;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
    background-color: #fafafa;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .section-title {
      font-size: 14px;
      font-weight: 500;
      color: var(--gray-700);
      margin: 0;
    }

    .panel-actions {
      display: flex;
      gap: 0px;
    }
  }

  .content {
    flex: 1;
    min-height: 0;
  }
}

.query-section,
.graph-section {
  .panel-section();

  .content {
    padding: 8px;
    flex: 1;
    overflow: hidden;
  }
}
</style>