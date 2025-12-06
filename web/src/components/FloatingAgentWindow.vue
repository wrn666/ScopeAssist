<template>
  <Teleport to="body">
    <div
      v-if="isVisible"
      class="floating-window"
      :class="{ 'minimized': isMinimized, 'dragging': isDragging }"
      :style="windowStyle"
      ref="windowRef"
    >
      <!-- 窗口头部 -->
      <div
        class="floating-window-header"
        @mousedown="startDrag"
        @dblclick="toggleMinimize"
      >
        <div class="header-title">
          <Bot size="16" stroke-width="2" />
          <span>{{ selectedAgent?.name || '智能体助手' }}</span>
        </div>
        <div class="header-actions">
          <button class="action-btn" @click="toggleMinimize" title="最小化">
            <MinusOutlined v-if="!isMinimized" />
            <ArrowsAltOutlined v-else />
          </button>
          <button class="action-btn close-btn" @click="close" title="关闭">
            <CloseOutlined />
          </button>
        </div>
      </div>

      <!-- 窗口内容 -->
      <div class="floating-window-body" v-show="!isMinimized">
        <AgentChatComponent
          :state="floatingState"
          :single-mode="true"
          @close-config-sidebar="() => floatingState.isConfigSidebarOpen = false"
        />
      </div>

      <!-- 调整大小手柄 -->
      <div
        v-show="!isMinimized"
        class="resize-handle"
        @mousedown="startResize"
      ></div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue';
import { MinusOutlined, CloseOutlined, ArrowsAltOutlined } from '@ant-design/icons-vue';
import { Bot } from 'lucide-vue-next';
import AgentChatComponent from './AgentChatComponent.vue';
import { useAgentStore } from '@/stores/agent';
import { storeToRefs } from 'pinia';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:visible', 'close']);

const agentStore = useAgentStore();
const { selectedAgent } = storeToRefs(agentStore);

// 为悬浮窗创建独立的状态
const floatingState = reactive({
  isConfigSidebarOpen: false,
  isSidebarOpen: false, // 悬浮窗不需要侧边栏
});

// 窗口状态
const isVisible = ref(props.visible);
const isMinimized = ref(false);
const isDragging = ref(false);
const isResizing = ref(false);

// 窗口位置和大小
const position = reactive({
  x: window.innerWidth - 420,
  y: window.innerHeight - 620,
});

const size = reactive({
  width: 400,
  height: 600,
});

// 拖拽起始位置
const dragStart = reactive({ x: 0, y: 0 });
const resizeStart = reactive({ x: 0, y: 0, width: 0, height: 0 });

const windowRef = ref(null);

// 窗口样式
const windowStyle = computed(() => {
  if (isMinimized.value) {
    return {
      left: `${position.x}px`,
      top: `${position.y}px`,
      width: '280px',
      height: 'auto',
    };
  }
  return {
    left: `${position.x}px`,
    top: `${position.y}px`,
    width: `${size.width}px`,
    height: `${size.height}px`,
  };
});

// 监听 visible prop 变化
watch(() => props.visible, (newVal) => {
  isVisible.value = newVal;
  if (newVal && isMinimized.value) {
    isMinimized.value = false;
  }
});

// 开始拖拽
const startDrag = (e) => {
  if (e.target.closest('.action-btn')) return;
  
  isDragging.value = true;
  dragStart.x = e.clientX - position.x;
  dragStart.y = e.clientY - position.y;

  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
  
  e.preventDefault();
};

// 拖拽中
const onDrag = (e) => {
  if (!isDragging.value) return;
  
  const newX = e.clientX - dragStart.x;
  const newY = e.clientY - dragStart.y;
  
  // 边界检测
  const maxX = window.innerWidth - (isMinimized.value ? 280 : size.width);
  const maxY = window.innerHeight - (isMinimized.value ? 50 : size.height);
  
  position.x = Math.max(0, Math.min(newX, maxX));
  position.y = Math.max(0, Math.min(newY, maxY));
};

// 停止拖拽
const stopDrag = () => {
  isDragging.value = false;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
};

// 开始调整大小
const startResize = (e) => {
  isResizing.value = true;
  resizeStart.x = e.clientX;
  resizeStart.y = e.clientY;
  resizeStart.width = size.width;
  resizeStart.height = size.height;

  document.addEventListener('mousemove', onResize);
  document.addEventListener('mouseup', stopResize);
  
  e.preventDefault();
  e.stopPropagation();
};

// 调整大小中
const onResize = (e) => {
  if (!isResizing.value) return;
  
  const deltaX = e.clientX - resizeStart.x;
  const deltaY = e.clientY - resizeStart.y;
  
  const newWidth = Math.max(320, Math.min(resizeStart.width + deltaX, window.innerWidth - position.x));
  const newHeight = Math.max(400, Math.min(resizeStart.height + deltaY, window.innerHeight - position.y));
  
  size.width = newWidth;
  size.height = newHeight;
};

// 停止调整大小
const stopResize = () => {
  isResizing.value = false;
  document.removeEventListener('mousemove', onResize);
  document.removeEventListener('mouseup', stopResize);
};

// 切换最小化
const toggleMinimize = () => {
  isMinimized.value = !isMinimized.value;
};

// 关闭窗口
const close = () => {
  isVisible.value = false;
  emit('update:visible', false);
  emit('close');
};

// 窗口大小调整时的边界检测
const handleWindowResize = () => {
  const maxX = window.innerWidth - (isMinimized.value ? 280 : size.width);
  const maxY = window.innerHeight - (isMinimized.value ? 50 : size.height);
  
  if (position.x > maxX) position.x = maxX;
  if (position.y > maxY) position.y = maxY;
};

// 监听窗口大小变化
if (typeof window !== 'undefined') {
  window.addEventListener('resize', handleWindowResize);
}
</script>

<style lang="less" scoped>
.floating-window {
  position: fixed;
  background: var(--bg-content);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 0 0 1px var(--gray-200);
  display: flex;
  flex-direction: column;
  z-index: 9999;
  transition: box-shadow 0.2s ease;
  overflow: hidden;

  &.dragging {
    cursor: move;
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.2), 0 0 0 1px var(--gray-300);
  }

  &.minimized {
    .floating-window-header {
      border-bottom: none;
    }
  }
}

.floating-window-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-sider);
  border-bottom: 1px solid var(--gray-200);
  cursor: move;
  user-select: none;

  .header-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    flex: 1;

    svg {
      flex-shrink: 0;
    }

    span {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .header-actions {
    display: flex;
    gap: 4px;
    align-items: center;

    .action-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border: none;
      background: transparent;
      border-radius: 6px;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.2s ease;
      font-size: 14px;

      &:hover {
        background: var(--gray-200);
        color: var(--text-primary);
      }

      &.close-btn:hover {
        background: #ff4d4f;
        color: white;
      }
    }
  }
}

.floating-window-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-content);

  // 隐藏悬浮窗中的侧边栏和相关控件
  :deep(.chat-container) {
    .sidebar-backdrop {
      display: none !important;
    }

    > :first-child {
      display: none !important; // 隐藏 ChatSidebarComponent
    }

    .chat {
      .chat-header {
        .header__left {
          .toggle-sidebar {
            display: none !important; // 隐藏侧边栏切换按钮
          }
        }
      }
    }
  }
}

.resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 16px;
  height: 16px;
  cursor: nwse-resize;
  
  &::after {
    content: '';
    position: absolute;
    right: 2px;
    bottom: 2px;
    width: 12px;
    height: 12px;
    background: 
      linear-gradient(135deg, transparent 50%, var(--gray-400) 50%),
      linear-gradient(135deg, transparent 60%, var(--gray-400) 60%);
    background-size: 8px 8px, 12px 12px;
    background-position: bottom right;
    background-repeat: no-repeat;
    opacity: 0.5;
  }

  &:hover::after {
    opacity: 0.8;
  }
}

// 响应式调整
@media (max-width: 768px) {
  .floating-window {
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    top: auto !important;
    width: 100% !important;
    max-height: 80vh;
    border-radius: 12px 12px 0 0;

    &.minimized {
      max-height: none;
      width: auto !important;
      left: auto !important;
      right: 16px !important;
      bottom: 16px !important;
    }
  }

  .resize-handle {
    display: none;
  }
}
</style>

