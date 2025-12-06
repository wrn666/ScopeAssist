import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { secureStorage } from '@/utils/secureStorage'

export const useUserStore = defineStore('user', () => {
  // 状态
  const token = ref(localStorage.getItem('user_token') || '')
  const userId = ref(parseInt(localStorage.getItem('user_id') || '0') || null)
  const username = ref(localStorage.getItem('username') || '')
  const userIdLogin = ref(localStorage.getItem('user_id_login') || '') // 用于登录的user_id
  const phoneNumber = ref(localStorage.getItem('phone_number') || '')
  const avatar = ref(localStorage.getItem('avatar') || '')
  const userRole = ref(localStorage.getItem('user_role') || '')

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userRole.value === 'admin' || userRole.value === 'superadmin')
  const isSuperAdmin = computed(() => userRole.value === 'superadmin')

  // 从加密存储恢复状态（自动登录）
  async function bootstrap() {
    try {
      // 优先从加密存储读取
      const encToken = await secureStorage.getDecrypted('user_token_secure')
      const encUserId = await secureStorage.getDecrypted('user_id_secure')
      const encUsername = await secureStorage.getDecrypted('username_secure')
      const encUserRole = await secureStorage.getDecrypted('user_role_secure')
      const encUserIdLogin = await secureStorage.getDecrypted('user_id_login_secure')
      const encPhoneNumber = await secureStorage.getDecrypted('phone_number_secure')
      const encAvatar = await secureStorage.getDecrypted('avatar_secure')

      if (encToken) token.value = encToken
      if (encUserId) userId.value = parseInt(encUserId) || null
      if (encUsername) username.value = encUsername
      if (encUserRole) userRole.value = encUserRole
      if (encUserIdLogin) userIdLogin.value = encUserIdLogin
      if (typeof encPhoneNumber === 'string') phoneNumber.value = encPhoneNumber
      if (typeof encAvatar === 'string') avatar.value = encAvatar
    } catch (e) {
      // 保持静默失败，避免阻塞应用启动
    }
  }

  // 动作
  async function login(credentials) {
    try {
      const formData = new FormData()
      // 支持user_id或phone_number登录
      formData.append('username', credentials.loginId) // 使用loginId作为通用登录标识
      formData.append('password', credentials.password)

      const response = await fetch('/api/auth/token', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()

        // 如果是423锁定状态码，抛出包含状态码的错误
        if (response.status === 423) {
          const lockError = new Error(error.detail || '账户被锁定')
          lockError.status = 423
          lockError.headers = response.headers
          throw lockError
        }

        throw new Error(error.detail || '登录失败')
      }

      const data = await response.json()

      // 更新状态
      token.value = data.access_token
      userId.value = data.user_id
      username.value = data.username
      userIdLogin.value = data.user_id_login
      phoneNumber.value = data.phone_number || ''
      avatar.value = data.avatar || ''
      userRole.value = data.role

      // 保存到本地存储（密文）
      await secureStorage.setEncrypted('user_token_secure', data.access_token)
      await secureStorage.setEncrypted('user_id_secure', String(data.user_id))
      await secureStorage.setEncrypted('username_secure', data.username)
      await secureStorage.setEncrypted('user_id_login_secure', data.user_id_login)
      await secureStorage.setEncrypted('phone_number_secure', data.phone_number || '')
      await secureStorage.setEncrypted('avatar_secure', data.avatar || '')
      await secureStorage.setEncrypted('user_role_secure', data.role)

      // 同步保留明文键（兼容旧逻辑）；如需严格安全可移除明文
      localStorage.setItem('user_token', data.access_token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('username', data.username)
      localStorage.setItem('user_id_login', data.user_id_login)
      localStorage.setItem('phone_number', data.phone_number || '')
      localStorage.setItem('avatar', data.avatar || '')
      localStorage.setItem('user_role', data.role)

      return true
    } catch (error) {
      console.error('登录错误:', error)
      throw error
    }
  }

  function logout() {
    // 清除状态
    token.value = ''
    userId.value = null
    username.value = ''
    userIdLogin.value = ''
    phoneNumber.value = ''
    avatar.value = ''
    userRole.value = ''

    // 清除本地存储（密文与明文）
    secureStorage.remove('user_token_secure')
    secureStorage.remove('user_id_secure')
    secureStorage.remove('username_secure')
    secureStorage.remove('user_id_login_secure')
    secureStorage.remove('phone_number_secure')
    secureStorage.remove('avatar_secure')
    secureStorage.remove('user_role_secure')

    localStorage.removeItem('user_token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('username')
    localStorage.removeItem('user_id_login')
    localStorage.removeItem('phone_number')
    localStorage.removeItem('avatar')
    localStorage.removeItem('user_role')
  }

  async function initialize(admin) {
    try {
      const response = await fetch('/api/auth/initialize', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(admin)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '初始化管理员失败')
      }

      const data = await response.json()

      // 更新状态
      token.value = data.access_token
      userId.value = data.user_id
      username.value = data.username
      userIdLogin.value = data.user_id_login
      phoneNumber.value = data.phone_number || ''
      avatar.value = data.avatar || ''
      userRole.value = data.role

      // 保存到本地存储（密文与明文）
      await secureStorage.setEncrypted('user_token_secure', data.access_token)
      await secureStorage.setEncrypted('user_id_secure', String(data.user_id))
      await secureStorage.setEncrypted('username_secure', data.username)
      await secureStorage.setEncrypted('user_id_login_secure', data.user_id_login)
      await secureStorage.setEncrypted('phone_number_secure', data.phone_number || '')
      await secureStorage.setEncrypted('avatar_secure', data.avatar || '')
      await secureStorage.setEncrypted('user_role_secure', data.role)

      localStorage.setItem('user_token', data.access_token)
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('username', data.username)
      localStorage.setItem('user_id_login', data.user_id_login)
      localStorage.setItem('phone_number', data.phone_number || '')
      localStorage.setItem('avatar', data.avatar || '')
      localStorage.setItem('user_role', data.role)

      return true
    } catch (error) {
      console.error('初始化管理员错误:', error)
      throw error
    }
  }

  async function checkFirstRun() {
    try {
      const response = await fetch('/api/auth/check-first-run')
      const data = await response.json()
      return data.first_run
    } catch (error) {
      console.error('检查首次运行状态错误:', error)
      return false
    }
  }

  // 公开注册普通用户（手机号为可选）
  async function register(userData) {
    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          username: userData.username,
          password: userData.password,
          phone_number: userData.phone_number || null
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '注册失败')
      }

      const data = await response.json()
      return data
    } catch (error) {
      console.error('注册错误:', error)
      throw error
    }
  }

  // 用于API请求的授权头
  function getAuthHeaders() {
    return {
      'Authorization': `Bearer ${token.value}`
    }
  }

  // 用户管理功能
  async function getUsers() {
    try {
      const response = await fetch('/api/auth/users', {
        headers: {
          ...getAuthHeaders()
        }
      })

      if (!response.ok) {
        throw new Error('获取用户列表失败')
      }

      return await response.json()
    } catch (error) {
      console.error('获取用户列表错误:', error)
      throw error
    }
  }

  async function createUser(userData) {
    try {
      const response = await fetch('/api/auth/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(userData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '创建用户失败')
      }

      return await response.json()
    } catch (error) {
      console.error('创建用户错误:', error)
      throw error
    }
  }

  async function updateUser(userId, userData) {
    try {
      const response = await fetch(`/api/auth/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(userData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '更新用户失败')
      }

      return await response.json()
    } catch (error) {
      console.error('更新用户错误:', error)
      throw error
    }
  }

  async function deleteUser(userId) {
    try {
      const response = await fetch(`/api/auth/users/${userId}`, {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders()
        }
      })

      if (!response.ok) {
        // 兼容后端返回非JSON错误（例如500返回HTML）
        let message = '删除用户失败'
        try {
          const errJson = await response.json()
          message = errJson.detail || errJson.message || message
        } catch (_) {
          const errText = await response.text()
          if (errText) message = errText
        }
        throw new Error(message)
      }

      // 正常返回JSON
      return await response.json()
    } catch (error) {
      console.error('删除用户错误:', error)
      throw error
    }
  }

  // 验证用户名并生成user_id
  async function validateUsernameAndGenerateUserId(username) {
    try {
      const response = await fetch('/api/auth/validate-username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({ username })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '用户名验证失败')
      }

      return await response.json()
    } catch (error) {
      console.error('用户名验证错误:', error)
      throw error
    }
  }

  // 上传头像
  async function uploadAvatar(file) {
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch('/api/auth/upload-avatar', {
        method: 'POST',
        headers: {
          ...getAuthHeaders()
        },
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '头像上传失败')
      }

      const data = await response.json()

      // 更新本地头像状态
      avatar.value = data.avatar_url
      localStorage.setItem('avatar', data.avatar_url)

      return data
    } catch (error) {
      console.error('头像上传错误:', error)
      throw error
    }
  }

  // 获取当前用户信息
  async function getCurrentUser() {
    try {
      const response = await fetch('/api/auth/me', {
        headers: {
          ...getAuthHeaders()
        }
      })

      if (!response.ok) {
        throw new Error('获取用户信息失败')
      }

      const userData = await response.json()

      // 更新本地状态
      username.value = userData.username
      userIdLogin.value = userData.user_id
      phoneNumber.value = userData.phone_number || ''
      avatar.value = userData.avatar || ''
      userRole.value = userData.role

      // 更新本地存储
      localStorage.setItem('username', userData.username)
      localStorage.setItem('user_id_login', userData.user_id)
      localStorage.setItem('phone_number', userData.phone_number || '')
      localStorage.setItem('avatar', userData.avatar || '')
      localStorage.setItem('user_role', userData.role)

      return userData
    } catch (error) {
      console.error('获取用户信息错误:', error)
      throw error
    }
  }

  // 更新个人资料
  async function updateProfile(profileData) {
    try {
      const response = await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify(profileData)
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '更新个人资料失败')
      }

      const userData = await response.json()

      // 更新本地状态
      if (typeof userData.username === 'string') {
        username.value = userData.username
        localStorage.setItem('username', userData.username)
      }
      if (typeof userData.phone_number !== 'undefined') {
        phoneNumber.value = userData.phone_number || ''
        localStorage.setItem('phone_number', userData.phone_number || '')
      }

      return userData
    } catch (error) {
      console.error('更新个人资料错误:', error)
      throw error
    }
  }

  return {
    // 状态
    token,
    userId,
    username,
    userIdLogin,
    phoneNumber,
    avatar,
    userRole,

    // 计算属性
    isLoggedIn,
    isAdmin,
    isSuperAdmin,

    // 方法
    bootstrap,
    login,
    logout,
    initialize,
    register,
    checkFirstRun,
    getAuthHeaders,
    getUsers,
    createUser,
    updateUser,
    deleteUser,
    validateUsernameAndGenerateUserId,
    uploadAvatar,
    getCurrentUser,
    updateProfile
  }
})

// 检查当前用户是否有管理员权限
export const checkAdminPermission = () => {
  const userStore = useUserStore()
  if (!userStore.isAdmin) {
    throw new Error('需要管理员权限')
  }
  return true
}

// 检查当前用户是否有超级管理员权限
export const checkSuperAdminPermission = () => {
  const userStore = useUserStore()
  if (!userStore.isSuperAdmin) {
    throw new Error('需要超级管理员权限')
  }
  return true
}
// 此处的 register 函数已移动到 store 内部，删除外部重复定义
