<template>
  <a-modal
    v-model:open="visible"
    title="编辑分块内容"
    width="800px"
    :confirmLoading="loading"
    @ok="handleSave"
    @cancel="handleCancel"
  >
    <a-form layout="vertical">
      <a-form-item label="Chunk ID">
        <a-input v-model:value="chunkInfo.chunk_id" disabled />
      </a-form-item>
      <a-form-item label="序号">
        <a-input-number v-model:value="chunkInfo.chunk_order_index" disabled style="width: 100%" />
      </a-form-item>
      <a-form-item label="内容" :required="true">
        <a-textarea
          v-model:value="chunkContent"
          :rows="15"
          placeholder="请输入分块内容"
          :maxlength="10000"
          show-count
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, watch } from 'vue';
import { message } from 'ant-design-vue';
import { documentApi } from '@/apis/knowledge_api';
import { useDatabaseStore } from '@/stores/database';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  chunk: {
    type: Object,
    default: null
  },
  dbId: {
    type: String,
    default: ''
  },
  fileId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:modelValue', 'saved']);

const store = useDatabaseStore();
const visible = ref(false);
const loading = ref(false);
const chunkContent = ref('');
const chunkInfo = ref({});

watch(() => props.modelValue, (newVal) => {
  visible.value = newVal;
  if (newVal && props.chunk) {
    chunkContent.value = props.chunk.content || '';
    chunkInfo.value = {
      chunk_id: props.chunk.id || props.chunk.chunk_id || '',
      chunk_order_index: props.chunk.chunk_order_index || 0
    };
  }
});

watch(visible, (newVal) => {
  emit('update:modelValue', newVal);
});

const handleSave = async () => {
  if (!chunkContent.value || !chunkContent.value.trim()) {
    message.error('内容不能为空');
    return;
  }

  if (!props.dbId || !props.fileId || !chunkInfo.value.chunk_id) {
    message.error('缺少必要参数');
    return;
  }

  loading.value = true;
  try {
    await documentApi.updateChunkContent(
      props.dbId,
      props.fileId,
      chunkInfo.value.chunk_id,
      chunkContent.value.trim()
    );
    message.success('分块内容更新成功');
    emit('saved');
    visible.value = false;
  } catch (error) {
    console.error('更新分块内容失败:', error);
    message.error(error.message || '更新失败，请稍后重试');
  } finally {
    loading.value = false;
  }
};

const handleCancel = () => {
  visible.value = false;
  chunkContent.value = '';
  chunkInfo.value = {};
};
</script>

<style scoped>
:deep(.ant-form-item-label) {
  font-weight: 500;
}
</style>

