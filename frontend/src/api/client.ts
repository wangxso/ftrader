import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000, // 增加到30秒，因为Binance API调用可能需要更长时间
  headers: {
    'Content-Type': 'application/json',
  },
})

export default apiClient
