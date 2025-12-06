<template>
  <img
    :src="imageSrc"
    :alt="alt"
    @error="handleError"
    class="codehub-image"
  />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useUserStore } from '@/stores/user';

const props = defineProps({
  src: {
    type: String,
    required: true,
  },
  alt: {
    type: String,
    default: '',
  },
});

const imageSrc = ref('');
const userStore = useUserStore();

// 加载图片
const loadImage = async () => {
  if (!props.src) return;
  
  // 如果是完整的 URL 或 blob URL，直接使用
  if (props.src.startsWith('http://') || props.src.startsWith('https://') || props.src.startsWith('blob:') || props.src.startsWith('data:')) {
    imageSrc.value = props.src;
    return;
  }
  
  // 如果是相对路径，通过 fetch 获取并转换为 blob URL
  try {
    const response = await fetch(props.src, {
      headers: {
        ...userStore.getAuthHeaders(),
      },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to load image: ${response.status}`);
    }
    
    const blob = await response.blob();
    imageSrc.value = URL.createObjectURL(blob);
  } catch (error) {
    console.error('加载图片失败:', error);
    // 加载失败时显示占位符
    imageSrc.value = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+';
  }
};

// 处理图片加载错误
const handleError = () => {
  // 已经设置了占位符，这里可以添加额外的错误处理
  console.error('图片加载失败:', props.src);
};

// 清理 blob URL
const cleanup = () => {
  if (imageSrc.value && imageSrc.value.startsWith('blob:')) {
    URL.revokeObjectURL(imageSrc.value);
  }
};

onMounted(() => {
  loadImage();
});

watch(() => props.src, () => {
  cleanup();
  loadImage();
});

// 组件卸载时清理
import { onUnmounted } from 'vue';
onUnmounted(() => {
  cleanup();
});
</script>

<style scoped>
.codehub-image {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 16px 0;
}
</style>

