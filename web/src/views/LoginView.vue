<template>
  <div class="login-view" :class="{ 'has-alert': serverStatus === 'error' }">
    <!-- 服务状态提示 -->
    <div v-if="serverStatus === 'error'" class="server-status-alert">
      <div class="alert-content">
        <exclamation-circle-outlined class="alert-icon" />
        <div class="alert-text">
          <div class="alert-title">服务端连接失败</div>
          <div class="alert-message">{{ serverError }}</div>
        </div>
        <a-button type="link" size="small" @click="checkServerHealth" :loading="healthChecking">
          重试
        </a-button>
      </div>
    </div>

    <div class="login-layout">
      <!-- 左侧图片区域 -->
      <div class="login-image-section">
        <img :src="loginBgImage" alt="登录背景" class="login-bg-image" />
        <div class="image-overlay">
          <div class="brand-info">
             <h1 class="brand-title">
               <div>ScopeAssist——</div>
               <div>基于魔搭的社区智答助手</div>
             </h1>
             <p class="brand-subtitle">{{ infoStore.branding?.subtitle || '大模型驱动的知识库管理工具' }}</p>
             <p class="brand-description">{{ infoStore.branding?.description || '结合知识库与知识图谱，提供更准确、更全面的回答' }}</p>
           </div>
          <div class="brand-copyright">
            <p>© ScopeAssist 2025 v0.2.0. {{ infoStore.branding?.copyright || '版权所有' }}</p>
          </div>
        </div>
      </div>

      <!-- 右侧登录表单区域 -->
      <div class="login-form-section">
        <div class="login-container">
      <div class="login-logo">
        <h1>欢迎登录 ScopeAssist</h1>
      </div>

      <!-- 初始化管理员表单 -->
      <div v-if="isFirstRun" class="login-form">
        <h2>系统初始化，请创建超级管理员账户</h2>
        <div class="init-tips">
          <p>• 请输入用户ID（仅支持字母、数字和下划线）</p>
          <p>• 手机号可选填写，用于后续登录</p>
          <p>• 请妥善保管管理员账户信息</p>
        </div>

        <a-form
          :model="adminForm"
          @finish="handleInitialize"
          layout="vertical"
        >
          <a-form-item
            label="用户ID"
            name="user_id"
            :rules="[
              { required: true, message: '请输入用户ID' },
              {
                pattern: /^[a-zA-Z0-9_]+$/,
                message: '用户ID只能包含字母、数字和下划线'
              },
              {
                min: 3,
                max: 20,
                message: '用户ID长度必须在3-20个字符之间'
              }
            ]"
          >
            <a-input
              v-model:value="adminForm.user_id"
              placeholder="请输入用户ID（3-20个字符）"
              :maxlength="20"
            />
          </a-form-item>

          <a-form-item
            label="手机号（可选）"
            name="phone_number"
            :rules="[
              {
                validator: async (rule, value) => {
                  if (!value || value.trim() === '') {
                    return; // 空值允许
                  }
                  const phoneRegex = /^1[3-9]\d{9}$/;
                  if (!phoneRegex.test(value)) {
                    throw new Error('请输入正确的手机号格式');
                  }
                }
              }
            ]"
          >
            <a-input
              v-model:value="adminForm.phone_number"
              placeholder="可用于登录，可不填写"
              :max-length="11"
            />
          </a-form-item>

          <a-form-item
            label="密码"
            name="password"
            :rules="[{ required: true, message: '请输入密码' }]"
          >
            <a-input-password v-model:value="adminForm.password" prefix-icon="lock" />
          </a-form-item>

          <a-form-item
            label="确认密码"
            name="confirmPassword"
            :rules="[
              { required: true, message: '请确认密码' },
              { validator: validateConfirmPassword }
            ]"
          >
            <a-input-password v-model:value="adminForm.confirmPassword" prefix-icon="lock" />
          </a-form-item>

          <a-form-item>
            <a-button type="primary" html-type="submit" :loading="loading" block>创建管理员账户</a-button>
          </a-form-item>
        </a-form>
      </div>

      <!-- 登录表单 -->
      <div v-else class="login-form">
        <template v-if="!isRegistering">
          <a-form
            :model="loginForm"
            @finish="handleLogin"
            layout="vertical"
          >
            <!-- 已移除“登录用户类型选择”，系统将根据账号自动识别角色 -->
            <a-form-item
              label="登录账号"
              name="loginId"
              :rules="[{ required: true, message: '请输入用户ID或手机号' }]"
            >
              <a-input v-model:value="loginForm.loginId" placeholder="用户ID或手机号">
                <template #prefix>
                  <user-outlined />
                </template>
              </a-input>
            </a-form-item>

            <a-form-item
              label="密码"
              name="password"
              :rules="[{ required: true, message: '请输入密码' }]"
            >
              <a-input-password v-model:value="loginForm.password">
                <template #prefix>
                  <lock-outlined />
                </template>
              </a-input-password>
            </a-form-item>

            <a-form-item>
              <div class="login-options">
                <a-checkbox v-model:checked="rememberMe" @click="showDevMessage">记住我</a-checkbox>
                <a class="forgot-password" @click="showDevMessage">忘记密码?</a>
              </div>
            </a-form-item>

            <a-form-item>
              <a-button
                type="primary"
                html-type="submit"
                :loading="loading"
                :disabled="isLocked"
                block
              >
                <span v-if="isLocked">账户已锁定 {{ formatTime(lockRemainingTime) }}</span>
                <span v-else>登录</span>
              </a-button>
            </a-form-item>

            <div class="switch-auth">
              还没有账号？
              <a-button type="link" @click="toggleRegister">创建新账号</a-button>
            </div>
          </a-form>
        </template>

        <template v-else>
          <!-- 注册表单 -->
          <a-form :model="registerForm" @finish="handleRegister" layout="vertical">
            <a-form-item label="用户名" name="username" :rules="registerUsernameRules">
              <a-input v-model:value="registerForm.username" placeholder="支持中文、英文、数字和下划线，2-20个字符" />
            </a-form-item>

            <a-form-item label="密码" name="password" :rules="registerPasswordRules">
              <a-input-password v-model:value="registerForm.password" />
            </a-form-item>

            <a-form-item label="确认密码" name="confirmPassword" :rules="[{ validator: validateRegisterConfirmPassword }]">
              <a-input-password v-model:value="registerForm.confirmPassword" />
            </a-form-item>

            <a-form-item label="手机号（可选）" name="phone_number" :rules="registerPhoneRules">
              <a-input v-model:value="registerForm.phone_number" placeholder="请输入手机号（可选，可用于登录）" />
            </a-form-item>

            <a-form-item>
              <a-button type="primary" html-type="submit" :loading="loading" block>
                创建账户并登录
              </a-button>
            </a-form-item>

            <div class="switch-auth">
              已有账号？
              <a-button type="link" @click="toggleRegister">返回登录</a-button>
            </div>
          </a-form>
        </template>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

          <!-- 页脚：移除第三方链接，保持页面简洁 -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { useInfoStore } from '@/stores/info';
import { useAgentStore } from '@/stores/agent';
import { message } from 'ant-design-vue';
import { healthApi } from '@/apis/system_api';
import { UserOutlined, LockOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';
const router = useRouter();
const userStore = useUserStore();
const infoStore = useInfoStore();
const agentStore = useAgentStore();

// 从infoStore获取登录背景图片
const loginBgImage = computed(() => {
  return infoStore.organization?.login_bg || '/login-bg.jpg';
});

// 状态
const isFirstRun = ref(false);
const loading = ref(false);
// 登录类型选择已移除（按照账号自动识别角色）
const errorMessage = ref('');
const rememberMe = ref(false);
const serverStatus = ref('loading');
const serverError = ref('');
const healthChecking = ref(false);
// 登录/注册视图切换
const isRegistering = ref(false);

// 登录锁定相关状态
const isLocked = ref(false);
const lockRemainingTime = ref(0);
const lockCountdown = ref(null);

// 登录表单
const loginForm = reactive({
  loginId: '', // 支持user_id或phone_number登录
  password: ''
});

// 管理员初始化表单
const adminForm = reactive({
  user_id: '', // 改为直接输入user_id
  password: '',
  confirmPassword: '',
  phone_number: '' // 手机号字段（可选）
});

// 注册表单
const registerForm = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  phone_number: ''
});

// 开发中功能提示
const showDevMessage = () => {
  message.info('该功能正在开发中，敬请期待！');
};

// 清理倒计时器
const clearLockCountdown = () => {
  if (lockCountdown.value) {
    clearInterval(lockCountdown.value);
    lockCountdown.value = null;
  }
};

// 启动锁定倒计时
const startLockCountdown = (remainingSeconds) => {
  clearLockCountdown();
  isLocked.value = true;
  lockRemainingTime.value = remainingSeconds;

  lockCountdown.value = setInterval(() => {
    lockRemainingTime.value--;
    if (lockRemainingTime.value <= 0) {
      clearLockCountdown();
      isLocked.value = false;
      errorMessage.value = '';
    }
  }, 1000);
};

// 格式化时间显示
const formatTime = (seconds) => {
  if (seconds < 60) {
    return `${seconds}秒`;
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}分${remainingSeconds}秒`;
  } else if (seconds < 86400) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}小时${minutes}分钟`;
  } else {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return `${days}天${hours}小时`;
  }
};

// 密码确认验证
const validateConfirmPassword = async (rule, value) => {
  if (value === '') {
    throw new Error('请确认密码');
  }
  if (value !== adminForm.password) {
    throw new Error('两次输入的密码不一致');
  }
};

// 注册表单规则
const registerUsernameRules = [
  { required: true, message: '请输入用户名' },
  { min: 2, max: 20, message: '用户名长度需在2-20个字符' },
  { pattern: /^[\u4e00-\u9fa5a-zA-Z0-9_]+$/, message: '用户名只能包含中文、英文、数字和下划线' }
];
const registerPasswordRules = [
  { required: true, message: '请输入密码' },
  { min: 6, message: '密码长度至少为6位' }
];
const registerPhoneRules = [
  {
    validator: async (rule, value) => {
      if (!value) return Promise.resolve(); // 如果值为空，则不进行校验
      const phoneRegex = /^1[3-9]\d{9}$/;
      if (!phoneRegex.test((value || '').replace(/[\s\-\(\)]/g, ''))) {
        return Promise.reject('请输入正确的手机号格式');
      }
      return Promise.resolve();
    }
  }
];
const validateRegisterConfirmPassword = async (rule, value) => {
  if (value === '') {
    throw new Error('请确认密码');
  }
  if (value !== registerForm.password) {
    throw new Error('两次输入的密码不一致');
  }
};

// 视图切换
const toggleRegister = () => {
  isRegistering.value = !isRegistering.value;
  errorMessage.value = '';
};

// 处理登录
const handleLogin = async () => {
  // 如果当前被锁定，不允许登录
  if (isLocked.value) {
    message.warning(`账户被锁定，请等待 ${formatTime(lockRemainingTime.value)}`);
    return;
  }

  try {
    loading.value = true;
    errorMessage.value = '';
    clearLockCountdown();

    await userStore.login({
      loginId: loginForm.loginId,
      password: loginForm.password
    });

    message.success('登录成功');

    // 获取重定向路径
    const redirectPath = sessionStorage.getItem('redirect') || '/';
    sessionStorage.removeItem('redirect'); // 清除重定向信息

    // 登录类型选择已移除，直接基于账号识别角色

    // 登录成功后默认跳转到首页
    router.push('/');
    return;
  } catch (error) {
    console.error('登录失败:', error);

    // 检查是否是锁定错误（HTTP 423）
    if (error.status === 423) {
      // 尝试从响应头中获取剩余时间
      let remainingTime = 0;
      if (error.headers && error.headers.get) {
        const lockRemainingHeader = error.headers.get('X-Lock-Remaining');
        if (lockRemainingHeader) {
          remainingTime = parseInt(lockRemainingHeader);
        }
      }

      // 如果没有从头中获取到，尝试从错误消息中解析
      if (remainingTime === 0) {
        const lockTimeMatch = error.message.match(/(\d+)\s*秒/);
        if (lockTimeMatch) {
          remainingTime = parseInt(lockTimeMatch[1]);
        }
      }

      if (remainingTime > 0) {
        startLockCountdown(remainingTime);
        errorMessage.value = `由于多次登录失败，账户已被锁定 ${formatTime(remainingTime)}`;
      } else {
        errorMessage.value = error.message || '账户被锁定，请稍后再试';
      }
    } else {
      errorMessage.value = error.message || '登录失败，请检查用户名和密码';
    }
  } finally {
    loading.value = false;
  }
};

// 处理注册
const handleRegister = async () => {
  try {
    loading.value = true;
    errorMessage.value = '';

    if (registerForm.password !== registerForm.confirmPassword) {
      errorMessage.value = '两次输入的密码不一致';
      return;
    }

    const result = await userStore.register({
      username: registerForm.username,
      password: registerForm.password,
      phone_number: registerForm.phone_number || null
    });

    // 自动登录：使用返回的 user_id + 注册密码
    await userStore.login({
      loginId: result.user_id,
      password: registerForm.password
    });

    message.success('注册并登录成功');
    router.push('/');
  } catch (error) {
    console.error('注册失败:', error);
    errorMessage.value = error.message || '注册失败，请检查输入';
  } finally {
    loading.value = false;
  }
};

// 处理初始化管理员
const handleInitialize = async () => {
  try {
    loading.value = true;
    errorMessage.value = '';

    if (adminForm.password !== adminForm.confirmPassword) {
      errorMessage.value = '两次输入的密码不一致';
      return;
    }

    await userStore.initialize({
      user_id: adminForm.user_id,
      password: adminForm.password,
      phone_number: adminForm.phone_number || null // 空字符串转为null
    });

    message.success('管理员账户创建成功');
    router.push('/');
  } catch (error) {
    console.error('初始化失败:', error);
    errorMessage.value = error.message || '初始化失败，请重试';
  } finally {
    loading.value = false;
  }
};

// 检查是否是首次运行
const checkFirstRunStatus = async () => {
  try {
    loading.value = true;
    const isFirst = await userStore.checkFirstRun();
    isFirstRun.value = isFirst;
  } catch (error) {
    console.error('检查首次运行状态失败:', error);
    errorMessage.value = '系统出错，请稍后重试';
  } finally {
    loading.value = false;
  }
};

// 检查服务器健康状态
const checkServerHealth = async () => {
  try {
    healthChecking.value = true;
    const response = await healthApi.checkHealth();
    if (response.status === 'ok') {
      serverStatus.value = 'ok';
    } else {
      serverStatus.value = 'error';
      serverError.value = response.message || '服务端状态异常';
    }
  } catch (error) {
    console.error('检查服务器健康状态失败:', error);
    serverStatus.value = 'error';
    serverError.value = error.message || '无法连接到服务端，请检查网络连接';
  } finally {
    healthChecking.value = false;
  }
};

// 组件挂载时
onMounted(async () => {
  // 如果已登录，跳转到首页
  if (userStore.isLoggedIn) {
    router.push('/');
    return;
  }

  // 首先检查服务器健康状态
  await checkServerHealth();

  // 检查是否是首次运行
  await checkFirstRunStatus();
});

// 组件卸载时清理定时器
onUnmounted(() => {
  clearLockCountdown();
});
</script>

<style lang="less" scoped>
.login-view {
  height: 100vh;
  width: 100%;
  position: relative;
  padding-top: 0;

  &.has-alert {
    padding-top: 60px;
  }
}

.login-layout {
  display: flex;
  height: 100%;
  width: 100%;
}

.login-image-section {
  flex: 0 0 55%;
  position: relative;
  overflow: hidden;

  .login-bg-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
  }

  .image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 80px 60px 40px 60px;
}

  .brand-info {
     text-align: left;
     color: white;
     max-width: 600px;

     .brand-title {
       font-size: 56px;
       font-weight: 800;
       margin-bottom: 24px;
       text-shadow: 0 3px 6px rgba(0, 0, 0, 0.4);
       letter-spacing: -1px;
       line-height: 1.2;
     }

     .brand-title div {
       white-space: nowrap;
     }

     .brand-subtitle {
       font-size: 28px;
       font-weight: 500;
       margin-bottom: 32px;
       opacity: 0.95;
       text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
       line-height: 1.3;
     }

     .brand-description {
       font-size: 20px;
       line-height: 1.6;
       margin-bottom: 0;
       opacity: 0.85;
       text-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
     }
   }

  .brand-copyright {
    align-self: flex-start;

    p {
      margin: 0;
      font-size: 14px;
      color: rgba(255, 255, 255, 0.7);
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
      font-weight: 400;
    }
  }
}

.login-form-section {
  flex: 1;
  min-width: 400px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #ffffff;
  padding: 40px;
}

.login-container {
  width: 100%;
  max-width: 420px;
  padding: 0;
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  backdrop-filter: none;
  border: none;
}

.login-logo {
  text-align: center;
  margin-bottom: 30px;

  img {
    height: 70px;
    margin-bottom: 16px;
  }

  h1 {
    font-size: 28px;
    font-weight: 600;
    color: var(--main-color);
    margin: 0;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
}

.login-form {
  h2 {
    text-align: center;
    margin-bottom: 30px;
    font-size: 22px;
    font-weight: 500;
    color: #333;
  }

  :deep(.ant-form-item) {
    margin-bottom: 20px;
  }

  :deep(.ant-input-affix-wrapper) {
    padding: 10px 11px;
    height: auto;
  }

  :deep(.ant-btn) {
    font-size: 16px;
    padding: 0.5rem;
    height: auto;
  }
}

.login-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;

  .forgot-password {
    color: #1890ff;
    font-size: 14px;

    &:hover {
      color: #40a9ff;
    }
  }
}

.login-type-tips {
  display: none;
}

.init-tips {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 20px;
  text-align: left;

  p {
    margin: 4px 0;
    font-size: 13px;
    color: #52c41a;
    line-height: 1.4;

    &:first-child {
      margin-top: 0;
    }

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.error-message {
  margin-top: 16px;
  padding: 10px 12px;
  background-color: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  color: #ff4d4f;
  font-size: 14px;
}

.switch-auth {
  margin-top: 8px;
  text-align: right;
}

.server-status-alert {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  padding: 12px 20px;
  background: linear-gradient(135deg, #ff4d4f, #ff7875);
  color: white;
  z-index: 1000;
  box-shadow: 0 2px 8px rgba(255, 77, 79, 0.3);

  .alert-content {
    display: flex;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;

    .alert-icon {
      font-size: 20px;
      margin-right: 12px;
      color: white;
    }

    .alert-text {
      flex: 1;

      .alert-title {
        font-weight: 600;
        font-size: 16px;
        margin-bottom: 2px;
      }

      .alert-message {
        font-size: 14px;
        opacity: 0.9;
      }
    }

    :deep(.ant-btn-link) {
      color: white;
      border-color: white;

      &:hover {
        color: white;
        background-color: rgba(255, 255, 255, 0.1);
      }
    }
  }
}
</style>
