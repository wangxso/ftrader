import apiClient from './client'

export interface TemplateInfo {
  id: string
  name: string
  description: string
  category: string
}

export interface TemplateDetail extends TemplateInfo {
  config_yaml: string
}

export const templatesApi = {
  // 获取所有模板
  getAll: async (): Promise<TemplateInfo[]> => {
    const response = await apiClient.get('/templates')
    return response.data
  },

  // 获取模板详情
  getById: async (id: string): Promise<TemplateDetail> => {
    const response = await apiClient.get(`/templates/${id}`)
    return response.data
  },
}
