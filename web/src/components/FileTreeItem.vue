<template>
  <div class="file-tree-item">
    <div
      class="tree-node"
      :class="{ active: isActive, 'is-directory': item.type === 'directory' }"
      @click="handleClick"
    >
      <span class="node-icon">
        <Folder v-if="item.type === 'directory'" size="16" />
        <File v-else size="16" />
      </span>
      <span class="node-name">{{ item.name }}</span>
      <span v-if="item.size" class="node-size">{{ formatSize(item.size) }}</span>
    </div>
    <div v-if="isExpanded && item.type === 'directory' && children" class="tree-children">
      <FileTreeItem
        v-for="child in children"
        :key="child.path"
        :item="child"
        :current-path="currentPath"
        :repo-name="repoName"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { Folder, File } from 'lucide-vue-next';
import { codehubApi } from '@/apis/codehub_api';
import { message } from 'ant-design-vue';

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  currentPath: {
    type: String,
    default: '',
  },
  repoName: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(['select']);

const isExpanded = ref(false);
const children = ref(null);
const loading = ref(false);

const isActive = computed(() => {
  return props.currentPath === props.item.path;
});

const handleClick = async () => {
  if (props.item.type === 'directory') {
    // 切换展开/收起
    if (isExpanded.value && children.value) {
      isExpanded.value = false;
    } else {
      isExpanded.value = true;
      if (!children.value && !loading.value) {
        await loadChildren();
      }
    }
  } else {
    // 选择文件
    emit('select', props.item.path);
  }
};

const loadChildren = async () => {
  if (loading.value) return;
  
  loading.value = true;
  try {
    const response = await codehubApi.getRepositoryTree(props.repoName, props.item.path);
    if (response.type === 'directory') {
      children.value = response.tree || [];
    }
  } catch (error) {
    console.error('加载子节点失败:', error);
    message.error('加载目录失败');
  } finally {
    loading.value = false;
  }
};

const formatSize = (bytes) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
};
</script>

<style scoped lang="less">
.file-tree-item {
  user-select: none;
}

.tree-node {
  display: flex;
  align-items: center;
  padding: 6px 8px;
  cursor: pointer;
  border-radius: 4px;
  gap: 8px;
  transition: background-color 0.2s;
  
  &:hover {
    background-color: var(--gray-100);
  }
  
  &.active {
    background-color: var(--main-30);
    color: var(--main-color);
  }
  
  .node-icon {
    display: flex;
    align-items: center;
    color: var(--gray-600);
    flex-shrink: 0;
  }
  
  .node-name {
    flex: 1;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .node-size {
    font-size: 11px;
    color: var(--gray-500);
    flex-shrink: 0;
  }
  
  &.is-directory {
    font-weight: 500;
  }
}

.tree-children {
  margin-left: 16px;
  border-left: 1px solid var(--gray-200);
  padding-left: 8px;
}
</style>

