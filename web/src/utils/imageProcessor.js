/**
 * 图片处理工具类
 * 用于压缩、转换和验证图片
 */

export class ImageProcessor {
  /**
   * 将文件转换为Base64
   * @param {File} file - 文件对象
   * @returns {Promise<string>} Base64字符串
   */
  static async fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * 压缩图片
   * @param {File} file - 图片文件
   * @param {Object} options - 压缩选项
   * @returns {Promise<string>} 压缩后的Base64字符串
   */
  static async compressImage(file, options = {}) {
    const {
      maxWidth = 1024,
      maxHeight = 1024,
      quality = 0.8,
      mimeType = 'image/jpeg'
    } = options;

    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const img = new Image();
        
        img.onload = () => {
          // 计算压缩后的尺寸
          let { width, height } = img;
          
          if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width = Math.floor(width * ratio);
            height = Math.floor(height * ratio);
          }

          // 创建canvas进行压缩
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);
          
          // 转换为Base64
          const compressedBase64 = canvas.toDataURL(mimeType, quality);
          resolve(compressedBase64);
        };
        
        img.onerror = reject;
        img.src = e.target.result;
      };
      
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * 创建图片预览URL
   * @param {File} file - 图片文件
   * @returns {Promise<string>} 预览URL
   */
  static async createPreviewUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /**
   * 验证图片文件
   * @param {File} file - 文件对象
   * @param {Object} options - 验证选项
   * @returns {Object} 验证结果
   */
  static validateImage(file, options = {}) {
    const {
      maxSize = 10 * 1024 * 1024, // 默认10MB
      allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    } = options;

    const errors = [];

    // 检查文件类型
    if (!allowedTypes.includes(file.type)) {
      errors.push(`不支持的图片格式: ${file.type}`);
    }

    // 检查文件大小
    if (file.size > maxSize) {
      const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(1);
      const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1);
      errors.push(`图片大小 ${fileSizeMB}MB 超过限制 ${maxSizeMB}MB`);
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * 批量处理图片
   * @param {FileList|Array<File>} files - 文件列表
   * @param {Object} options - 处理选项
   * @returns {Promise<Array>} 处理后的图片数据
   */
  static async processImages(files, options = {}) {
    const {
      compress = true,
      maxWidth = 1024,
      maxHeight = 1024,
      quality = 0.8
    } = options;

    const results = [];

    for (const file of Array.from(files)) {
      try {
        // 验证图片
        const validation = this.validateImage(file);
        if (!validation.valid) {
          results.push({
            name: file.name,
            error: validation.errors.join('; '),
            success: false
          });
          continue;
        }

        // 创建预览
        const preview = await this.createPreviewUrl(file);

        // 处理图片
        let base64;
        if (compress) {
          base64 = await this.compressImage(file, { maxWidth, maxHeight, quality });
        } else {
          base64 = await this.fileToBase64(file);
        }

        results.push({
          name: file.name,
          size: file.size,
          type: file.type,
          preview,
          base64,
          success: true
        });
      } catch (error) {
        console.error(`处理图片 ${file.name} 失败:`, error);
        results.push({
          name: file.name,
          error: error.message,
          success: false
        });
      }
    }

    return results;
  }

  /**
   * 从Base64获取图片信息
   * @param {string} base64 - Base64字符串
   * @returns {Object} 图片信息
   */
  static getImageInfoFromBase64(base64) {
    // 提取MIME类型
    const matches = base64.match(/^data:([A-Za-z-+\/]+);base64,/);
    const mimeType = matches ? matches[1] : 'image/jpeg';
    
    // 计算大小（Base64字符串长度 * 0.75 约等于原始字节大小）
    const base64Data = base64.split(',')[1] || base64;
    const size = Math.round((base64Data.length * 3) / 4);

    return {
      mimeType,
      size,
      isValid: !!matches
    };
  }

  /**
   * 批量压缩图片Base64数组
   * @param {Array<string>} base64Array - Base64字符串数组
   * @param {Object} options - 压缩选项
   * @returns {Promise<Array<string>>} 压缩后的Base64数组
   */
  static async compressBase64Array(base64Array, options = {}) {
    const results = [];
    
    for (const base64 of base64Array) {
      try {
        // 将Base64转为Blob
        const response = await fetch(base64);
        const blob = await response.blob();
        const file = new File([blob], 'image.jpg', { type: blob.type });
        
        // 压缩
        const compressed = await this.compressImage(file, options);
        results.push(compressed);
      } catch (error) {
        console.error('压缩Base64失败:', error);
        results.push(base64); // 失败时返回原始数据
      }
    }
    
    return results;
  }
}

export default ImageProcessor;

