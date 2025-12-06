<template>
  <div class="codehub-repositories-container">
    <div class="panel-header">
      <div class="header-left">
        <h3>代码仓库</h3>
        <span class="repo-count">{{ repositories.length }} 个仓库</span>
      </div>
      <div class="header-actions">
        <a-button
          type="text"
          @click="handleRefresh"
          :loading="loading"
          :icon="h(ReloadOutlined)"
          title="刷新"
        />
      </div>
    </div>

    <div v-if="loading && repositories.length === 0" class="loading-container">
      <a-spin size="large" />
      <p>正在加载仓库列表...</p>
    </div>

    <div v-else-if="repositories.length === 0" class="empty-state">
      <div class="empty-icon">
        <FolderGit2 size="64" />
      </div>
      <h3>还没有代码仓库</h3>
      <p>使用 git clone 工具克隆仓库后，会在这里显示</p>
    </div>

    <div v-else class="repositories-list">
      <div
        v-for="repo in repositories"
        :key="repo.name"
        class="repo-item"
      >
        <div class="repo-info">
          <div class="repo-header">
            <FolderGit2 class="repo-icon" />
            <span class="repo-name">{{ repo.name }}</span>
            <a-tag v-if="repo.is_git_repo" color="blue" size="small">Git</a-tag>
            <a-tag v-if="isRepoBuilt(repo.name)" color="green" size="small">
              <template #icon>
                <CheckCircleOutlined />
              </template>
              已构建
            </a-tag>
          </div>
          <div v-if="repo.remote_url" class="repo-url">{{ repo.remote_url }}</div>
        </div>
        <div class="repo-actions">
          <a-button
            v-if="!isRepoBuilt(repo.name)"
            type="primary"
            size="small"
            @click="handleBuildGraph(repo.name)"
            :loading="buildingRepos.has(repo.name)"
            :disabled="buildingRepos.has(repo.name)"
          >
            <template #icon>
              <component :is="h(NetworkIcon)" />
            </template>
            构建知识图谱
          </a-button>
          <a-button
            v-else
            type="default"
            size="small"
            @click="handleRebuildGraph(repo.name)"
            :loading="buildingRepos.has(repo.name)"
            :disabled="buildingRepos.has(repo.name)"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            重新构建
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, h, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import { ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons-vue';
import { FolderGit2, Network } from 'lucide-vue-next';
import { codehubApi } from '@/apis/codehub_api';
import { useDatabaseStore } from '@/stores/database';

const NetworkIcon = Network;

const store = useDatabaseStore();
const databaseId = computed(() => store.databaseId);
const database = computed(() => store.database || {});

const repositories = ref([]);
const loading = ref(false);
const buildingRepos = ref(new Set());

// 检查仓库是否已构建
function isRepoBuilt(repoName) {
  const files = database.value.files || {};
  for (const fileId in files) {
    const file = files[fileId];
    if (file.filename === repoName && file.type === 'repository' && file.status === 'done') {
      return true;
    }
  }
  return false;
}

const loadRepositories = async () => {
  loading.value = true;
  try {
    const data = await codehubApi.getRepositories();
    repositories.value = data.repositories || [];
  } catch (error) {
    console.error('加载仓库列表失败:', error);
    message.error('加载仓库列表失败: ' + (error.message || '未知错误'));
  } finally {
    loading.value = false;
  }
};

const handleRefresh = () => {
  loadRepositories();
};

const handleBuildGraph = async (repoName) => {
  if (!databaseId.value) {
    message.error('知识库ID不存在');
    return;
  }

  buildingRepos.value.add(repoName);
  try {
    const result = await codehubApi.buildRepositoryGraph(repoName, databaseId.value);
    message.success(`成功为仓库 ${repoName} 构建知识图谱`);
    
    // 刷新文件列表
    await store.getDatabaseInfo(databaseId.value);
  } catch (error) {
    console.error('构建知识图谱失败:', error);
    message.error('构建知识图谱失败: ' + (error.message || '未知错误'));
  } finally {
    buildingRepos.value.delete(repoName);
  }
};

const handleRebuildGraph = async (repoName) => {
  if (!databaseId.value) {
    message.error('知识库ID不存在');
    return;
  }

  buildingRepos.value.add(repoName);
  try {
    const result = await codehubApi.buildRepositoryGraph(repoName, databaseId.value);
    message.success(`成功重新构建仓库 ${repoName} 的知识图谱`);
    
    // 刷新文件列表
    await store.getDatabaseInfo(databaseId.value);
  } catch (error) {
    console.error('重新构建知识图谱失败:', error);
    message.error('重新构建知识图谱失败: ' + (error.message || '未知错误'));
  } finally {
    buildingRepos.value.delete(repoName);
  }
};

// 监听知识库文件列表变化，更新构建状态
watch(() => database.value.files, () => {
  // 文件列表更新时，组件会自动重新渲染，isRepoBuilt 会重新计算
}, { deep: true });

onMounted(() => {
  loadRepositories();
});
</script>

<style lang="less" scoped>
.codehub-repositories-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-200);

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--gray-800);
    }

    .repo-count {
      font-size: 14px;
      color: var(--gray-500);
    }
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.loading-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--gray-500);
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--gray-500);

  .empty-icon {
    opacity: 0.5;
  }

  h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--gray-700);
  }

  p {
    margin: 0;
    font-size: 14px;
  }
}

.repositories-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.repo-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  transition: all 0.2s;

  &:hover {
    background: var(--gray-100);
    border-color: var(--main-color);
  }

  .repo-info {
    flex: 1;
    min-width: 0;

    .repo-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;

      .repo-icon {
        width: 20px;
        height: 20px;
        color: var(--main-color);
        flex-shrink: 0;
      }

      .repo-name {
        font-size: 15px;
        font-weight: 500;
        color: var(--gray-800);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .repo-url {
      font-size: 13px;
      color: var(--gray-500);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .repo-actions {
    flex-shrink: 0;
    margin-left: 16px;
  }
}
</style>

