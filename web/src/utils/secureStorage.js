// 简易安全存储封装：使用 Web Crypto AES-GCM 对敏感数据（如 token、user_id）加密存储
// 说明：前端加密无法防止已发生的 XSS；此实现用于提升基础隐私保护和避免明文存储
// 注意：当 Web Crypto API 不可用时（如通过 HTTP/IP 访问），会自动降级为普通 localStorage

const DEFAULT_SECRET = (import.meta && import.meta.env && import.meta.env.VITE_SECURE_STORAGE_KEY) || 'ScopeAssistSecureKey';

// 检查 Web Crypto API 是否可用
function isCryptoAvailable() {
  return typeof crypto !== 'undefined' && 
         crypto.subtle && 
         crypto.getRandomValues;
}

async function getKey(secret = DEFAULT_SECRET) {
  if (!isCryptoAvailable()) {
    throw new Error('Web Crypto API 不可用');
  }
  const enc = new TextEncoder();
  const secretBytes = enc.encode(secret);
  // 将秘密做一次 SHA-256，再导入为 AES-GCM 的原始密钥
  const hash = await crypto.subtle.digest('SHA-256', secretBytes);
  return crypto.subtle.importKey('raw', hash, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function fromBase64(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

export const secureStorage = {
  async encryptString(plaintext) {
    // 如果 Web Crypto API 不可用，直接返回明文（降级处理）
    if (!isCryptoAvailable()) {
      console.warn('Web Crypto API 不可用，使用明文存储（建议通过 HTTPS 访问以启用加密）');
      return plaintext;
    }
    
    try {
      const enc = new TextEncoder();
      const key = await getKey();
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, enc.encode(plaintext));
      const ivB64 = toBase64(iv);
      const ctB64 = toBase64(cipher);
      return `encrypted:${ivB64}:${ctB64}`;
    } catch (e) {
      console.warn('加密失败，使用明文存储:', e.message);
      return plaintext;
    }
  },

  async decryptString(payload) {
    if (!payload) return '';
    
    // 如果 Web Crypto API 不可用，尝试直接返回（可能是明文）
    if (!isCryptoAvailable()) {
      // 如果是加密格式，无法解密，返回空
      if (payload.startsWith('encrypted:')) {
        console.warn('Web Crypto API 不可用，无法解密已加密的数据');
        return '';
      }
      // 否则返回明文
      return payload;
    }
    
    try {
      let ivB64, ctB64;
      
      // 检查是否是加密格式
      if (payload.startsWith('encrypted:')) {
        // 新格式：encrypted:iv:ct
        const parts = payload.substring(10).split(':');
        if (parts.length !== 2) return '';
        [ivB64, ctB64] = parts;
      } else {
        // 兼容旧格式（没有 encrypted: 前缀）
        if (!payload.includes(':')) return payload;
        const parts = payload.split(':');
        if (parts.length !== 2) return payload;
        [ivB64, ctB64] = parts;
      }
      
      if (!ivB64 || !ctB64) return payload;
      
      const iv = new Uint8Array(fromBase64(ivB64));
      const cipher = fromBase64(ctB64);
      const key = await getKey();
      const plainBuf = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, cipher);
      const dec = new TextDecoder();
      return dec.decode(plainBuf);
    } catch (e) {
      // 解密失败时，尝试返回原始值（可能是明文）
      console.warn('解密失败，尝试返回原始值:', e.message);
      return payload;
    }
  },

  async setEncrypted(key, value) {
    const payload = await this.encryptString(String(value ?? ''));
    localStorage.setItem(key, payload);
  },

  async getDecrypted(key) {
    const payload = localStorage.getItem(key);
    if (!payload) return '';
    return await this.decryptString(payload);
  },

  remove(key) {
    localStorage.removeItem(key);
  }
};

