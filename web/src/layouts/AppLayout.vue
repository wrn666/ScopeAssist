<script setup>
import { ref, reactive, onMounted, useTemplateRef, computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import {
  GithubOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons-vue'
import { Bot, Waypoints, LibraryBig, Settings, BarChart3, ChevronLeft, ChevronRight, FolderGit2 } from 'lucide-vue-next';
import { onLongPress } from '@vueuse/core'

import { useConfigStore } from '@/stores/config'
import { useDatabaseStore } from '@/stores/database'
import { useInfoStore } from '@/stores/info'
import UserInfoComponent from '@/components/UserInfoComponent.vue'
import DebugComponent from '@/components/DebugComponent.vue'

const configStore = useConfigStore()
const databaseStore = useDatabaseStore()
const infoStore = useInfoStore()

const layoutSettings = reactive({
  showDebug: false,
  useTopBar: false, // 是否使用顶栏
  sidebarExpanded: localStorage.getItem('sidebarExpanded') === 'true' || false, // 侧边栏是否展开
})

// Add state for GitHub stars
const githubStars = ref(0)
const isLoadingStars = ref(false)

// Add state for debug modal
const showDebugModal = ref(false)
const htmlRefHook = useTemplateRef('htmlRefHook')

// Setup long press for debug modal
onLongPress(
  htmlRefHook,
  () => {
    console.log('long press')
    showDebugModal.value = true
  },
  {
    delay: 1000, // 1秒长按
    modifiers: {
      prevent: true
    }
  }
)

// Handle debug modal close
const handleDebugModalClose = () => {
  showDebugModal.value = false
}

const getRemoteConfig = () => {
  configStore.refreshConfig()
}

const getRemoteDatabase = () => {
  databaseStore.getDatabaseInfo()
}


onMounted(async () => {
  // 加载信息配置
  await infoStore.loadInfoConfig()
  // 加载其他配置
  getRemoteConfig()
  getRemoteDatabase()
  fetchGithubStars() // Fetch GitHub stars on mount
})

// 打印当前页面的路由信息，使用 vue3 的 setup composition API
const route = useRoute()
console.log(route)

// 切换侧边栏展开/收缩
const toggleSidebar = () => {
  layoutSettings.sidebarExpanded = !layoutSettings.sidebarExpanded
  localStorage.setItem('sidebarExpanded', layoutSettings.sidebarExpanded)
}

// 下面是导航菜单部分，添加智能体项
const mainList = [{
    name: '智能体',
    path: '/agent',
    icon: Bot,
    activeIcon: Bot,
  }, {
    name: '知识库',
    path: '/database',
    icon: LibraryBig,
    activeIcon: LibraryBig,
  }, {
    name: '代码仓库',
    path: '/codehub',
    icon: FolderGit2,
    activeIcon: FolderGit2,
  }, {
    name: '仪表盘',
    path: '/dashboard',
    icon: BarChart3,
    activeIcon: BarChart3,
  }
]
</script>

<template>
  <div class="app-layout" :class="{ 'use-top-bar': layoutSettings.useTopBar }">
    <div class="header" :class="{ 'top-bar': layoutSettings.useTopBar, 'expanded': layoutSettings.sidebarExpanded }">
      <div class="logo circle">
        <router-link to="/">
          <img :src="infoStore.organization.avatar">
          <span v-if="layoutSettings.sidebarExpanded" class="logo-text">ScopeAssist</span>
        </router-link>
      </div>
      <div class="nav">
        <!-- 使用mainList渲染导航项 -->
        <RouterLink
          v-for="(item, index) in mainList"
          :key="index"
          :to="item.path"
          v-show="!item.hidden"
          class="nav-item"
          active-class="active">
          <a-tooltip placement="right" :mouseEnterDelay="0.5" :disabled="layoutSettings.sidebarExpanded">
            <template #title>{{ item.name }}</template>
            <div class="nav-item-content">
              <component class="icon" :is="route.path.startsWith(item.path) ? item.activeIcon : item.icon" size="22"/>
              <span v-if="layoutSettings.sidebarExpanded" class="nav-text">{{ item.name }}</span>
            </div>
          </a-tooltip>
        </RouterLink>
      </div>
      <div
        ref="htmlRefHook"
        class="fill debug-trigger"
      ></div>

      <!-- <div class="nav-item api-docs">
        <a-tooltip placement="right">
          <template #title>接口文档 {{ apiDocsUrl }}</template>
          <a :href="apiDocsUrl" target="_blank" class="github-link">
            <ApiOutlined class="icon" style="color: #222;"/>
          </a>
        </a-tooltip>
      </div> -->

      <!-- 用户信息组件 -->
      <div class="nav-item user-info">
        <a-tooltip placement="right" :disabled="layoutSettings.sidebarExpanded">
          <template #title>用户信息</template>
          <div class="user-info-content">
            <UserInfoComponent :showRole="false" />
            <span v-if="layoutSettings.sidebarExpanded" class="nav-text user-info-text">用户信息</span>
          </div>
        </a-tooltip>
      </div>

      <RouterLink class="nav-item setting" to="/setting" active-class="active">
        <a-tooltip placement="right" :mouseEnterDelay="0.5" :disabled="layoutSettings.sidebarExpanded">
          <template #title>设置</template>
          <div class="nav-item-content">
            <Settings size="22"/>
            <span v-if="layoutSettings.sidebarExpanded" class="nav-text">设置</span>
          </div>
        </a-tooltip>
      </RouterLink>

      <!-- 收缩/展开按钮 -->
      <div class="toggle-sidebar-btn" @click="toggleSidebar">
        <ChevronLeft v-if="layoutSettings.sidebarExpanded" size="20" />
        <ChevronRight v-else size="20" />
      </div>
    </div>
    <div class="header-mobile">
      <RouterLink to="/chat" class="nav-item" active-class="active">对话</RouterLink>
      <RouterLink to="/database" class="nav-item" active-class="active">知识</RouterLink>
      <RouterLink to="/setting" class="nav-item" active-class="active">设置</RouterLink>
    </div>
    <router-view v-slot="{ Component, route }" id="app-router-view">
      <keep-alive v-if="route.meta.keepAlive !== false">
        <component :is="Component" />
      </keep-alive>
      <component :is="Component" v-else />
    </router-view>

    <!-- Debug Modal -->
    <a-modal
      v-model:open="showDebugModal"
      title="调试面板"
      width="90%"
      :footer="null"
      @cancel="handleDebugModalClose"
      :maskClosable="true"
      :destroyOnClose="true"
      class="debug-modal"
    >
      <DebugComponent />
    </a-modal>
  </div>
</template>

<style lang="less" scoped>
// Less 变量定义
@header-width-collapsed: 50px;
@header-width-expanded: 200px;

.app-layout {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100vh;
  min-width: var(--min-width);

  .header-mobile {
    display: none;
  }

  .debug-panel {
    position: absolute;
    z-index: 100;
    right: 0;
    bottom: 50px;
    border-radius: 20px 0 0 20px;
    cursor: pointer;
  }
}

div.header, #app-router-view {
  height: 100%;
  max-width: 100%;
  user-select: none;
}

#app-router-view {
  flex: 1 1 auto;
  overflow-y: auto;
}

.header {
  display: flex;
  flex-direction: column;
  flex: 0 0 @header-width-collapsed;
  justify-content: flex-start;
  align-items: center;
  background-color: var(--main-10);
  height: 100%;
  width: @header-width-collapsed;
  border-right: 1px solid var(--gray-100);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), 
              flex-basis 0.3s cubic-bezier(0.4, 0, 0.2, 1),
              padding 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: width;

  &.expanded {
    flex: 0 0 @header-width-expanded;
    width: @header-width-expanded;
    align-items: flex-start;
    padding: 0 12px;
  }

  .nav {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    position: relative;
    width: 100%;
    gap: 8px;
  }

  // 添加debug触发器样式
  .debug-trigger {
    position: relative;
    height: 100%;
    width: 100%;
    min-height: 20px;
    flex-grow: 1;
  }

  .logo {
    width: 34px;
    height: 34px;
    margin: 12px 0 20px 0;
    transition: width 0.3s ease;

    a {
      display: flex;
      align-items: center;
      gap: 10px;
      text-decoration: none;
      white-space: nowrap;
    }

    img {
      width: 34px;
      height: 34px;
      border-radius: 4px;
      flex-shrink: 0;
    }

    .logo-text {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      opacity: 0;
      animation: fadeIn 0.3s ease 0.15s forwards;
    }
  }

  &.expanded .logo {
    width: 100%;
  }

  .nav-item {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    padding: 10px;
    border: 1px solid transparent;
    border-radius: 8px;
    background-color: transparent;
    color: #222;
    font-size: 20px;
    transition: all 0.2s ease-in-out;
    margin: 0;
    text-decoration: none;
    cursor: pointer;
    position: relative;
    white-space: nowrap;

    .nav-item-content {
      display: flex;
      align-items: center;
      gap: 0;
      width: 100%;
    }

    .nav-text {
      margin-left: 12px;
      font-size: 15px;
      font-weight: 500;
      line-height: 22px;
      opacity: 0;
      animation: fadeIn 0.3s ease 0.15s forwards;
    }

    &.github {
      padding: 10px 12px;
      margin-bottom: 16px;
      &:hover {
        background-color: transparent;
        border: 1px solid transparent;
      }

      .github-link {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: inherit;
      }

      .github-stars {
        display: flex;
        align-items: center;
        font-size: 12px;
        margin-top: 4px;

        .star-icon {
          color: #f0a742;
          font-size: 12px;
          margin-right: 2px;
        }

        .star-count {
          font-weight: 600;
        }
      }
    }

    &.api-docs {
      padding: 10px 12px;
    }
    &.active {
      text-shadow: 0 0 15px var(--main-300);
      font-weight: bold;
      color: var(--main-color);
    }

    &.warning {
      color: red;
    }

    &:hover {
      color: var(--main-color);
    }
  }

  .setting {
    width: auto;
    font-size: 20px;
    color: #333;
    margin-bottom: 8px;
    padding: 16px 12px;

    &:hover {
      cursor: pointer;
    }
  }

  .toggle-sidebar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    background-color: transparent;
    color: var(--gray-700);
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: 12px;
    flex-shrink: 0;

    &:hover {
      background-color: var(--gray-100);
      color: var(--main-color);
    }
  }

  &.expanded {
    .nav-item {
      width: 100%;
      justify-content: flex-start;
      padding: 10px 12px;

      &.user-info {
        display: flex;
        align-items: center;
        gap: 0;
        
        .user-info-content {
          display: flex;
          align-items: center;
          gap: 0;
          width: 100%;
        }

        :deep(.user-info-component) {
          display: flex;
          align-items: center;
        }

        :deep(.user-info-dropdown) {
          display: flex;
          align-items: center;
          justify-content: flex-start;
        }

        :deep(.user-avatar) {
          width: 22px !important;
          height: 22px !important;
          
          .avatar-image {
            width: 22px !important;
            height: 22px !important;
          }

          svg {
            width: 22px;
            height: 22px;
          }
        }

        .user-info-text {
          margin-left: 12px;
        }
      }
    }

    .setting {
      width: 100%;
      justify-content: flex-start;
      padding: 10px 12px;
      margin-bottom: 0;
    }

    .toggle-sidebar-btn {
      width: 100%;
    }
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}


@media (max-width: 520px) {
  .app-layout {
    flex-direction: column-reverse;

    div.header {
      display: none;
    }

    .debug-panel {
      bottom: 10rem;
    }

  }
  .app-layout div.header-mobile {
    display: flex;
    flex-direction: row;
    width: 100%;
    padding: 0 20px;
    justify-content: space-around;
    align-items: center;
    flex: 0 0 60px;
    border-right: none;
    height: 40px;

    .nav-item {
      text-decoration: none;
      width: 40px;
      color: var(--gray-900);
      font-size: 1rem;
      font-weight: bold;
      transition: color 0.1s ease-in-out, font-size 0.1s ease-in-out;

      &.active {
        color: black;
        font-size: 1.1rem;
      }
    }
  }
  .app-layout .chat-box::webkit-scrollbar {
    width: 0;
  }
}

.app-layout.use-top-bar {
  flex-direction: column;
}

.header.top-bar {
  flex-direction: row;
  flex: 0 0 50px;
  width: 100%;
  height: 50px;
  border-right: none;
  border-bottom: 1px solid var(--main-40);
  background-color: var(--main-20);
  padding: 0 20px;
  gap: 24px;

  .logo {
    width: fit-content;
    height: 28px;
    margin-right: 16px;
    display: flex;
    align-items: center;

    a {
      display: flex;
      align-items: center;
      text-decoration: none;
      color: inherit;
    }

    img {
      width: 28px;
      height: 28px;
      margin-right: 8px;
    }

  }

  .nav {
    flex-direction: row;
    height: auto;
    gap: 20px;
  }

  .nav-item {
    flex-direction: row;
    width: auto;
    padding: 4px 16px;
    margin: 0;

    .icon {
      margin-right: 8px;
      font-size: 15px; // 减小图标大小
      border: none;
      outline: none;

      &:focus, &:active {
        border: none;
        outline: none;
      }
    }

    .text {
      margin-top: 0;
      font-size: 15px;
    }

    &.github, &.setting {
      padding: 8px 12px;

      .icon {
        margin-right: 0;
        font-size: 18px;
      }

      &.active {
        color: var(--main-color);
      }
    }

    &.github {
      a {
        display: flex;
        align-items: center;
      }

      .github-stars {
        display: flex;
        align-items: center;
        margin-left: 6px;

        .star-icon {
          color: #f0a742;
          font-size: 14px;
          margin-right: 2px;
        }
      }
    }
  }
}
</style>