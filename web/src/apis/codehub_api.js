import { apiGet, apiDelete, apiPost } from './base';

/**
 * CodeHub API - 代码仓库管理
 */
export const codehubApi = {
  /**
   * 获取用户的代码仓库列表
   * @returns {Promise} - 仓库列表
   */
  getRepositories: () => apiGet('/api/codehub/repositories'),

  /**
   * 获取仓库的文件树结构
   * @param {string} repoName - 仓库名称
   * @param {string} path - 相对路径，默认为根目录
   * @returns {Promise} - 文件树结构
   */
  getRepositoryTree: (repoName, path = '') => {
    const params = path ? `?path=${encodeURIComponent(path)}` : '';
    return apiGet(`/api/codehub/repositories/${encodeURIComponent(repoName)}/tree${params}`);
  },

  /**
   * 获取文件内容
   * @param {string} repoName - 仓库名称
   * @param {string} path - 文件相对路径
   * @returns {Promise} - 文件内容
   */
  getFileContent: (repoName, path) => {
    return apiGet(`/api/codehub/repositories/${encodeURIComponent(repoName)}/file?path=${encodeURIComponent(path)}`);
  },

  /**
   * 删除代码仓库
   * @param {string} repoName - 仓库名称
   * @returns {Promise} - 删除结果
   */
  deleteRepository: (repoName) => apiDelete(`/api/codehub/repositories/${encodeURIComponent(repoName)}`),

  /**
   * 为代码仓库构建知识图谱
   * @param {string} repoName - 仓库名称
   * @param {string} dbId - 知识库ID
   * @returns {Promise} - 构建结果
   */
  buildRepositoryGraph: (repoName, dbId) => {
    return apiPost(`/api/codehub/repositories/${encodeURIComponent(repoName)}/build-graph`, {
      db_id: dbId
    });
  },
};

