import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Strategies from '../views/Strategies.vue'
import StrategyDetail from '../views/StrategyDetail.vue'
import Account from '../views/Account.vue'
import Backtest from '../views/Backtest.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: Dashboard,
    },
    {
      path: '/strategies',
      name: 'Strategies',
      component: Strategies,
    },
    {
      path: '/strategies/:id',
      name: 'StrategyDetail',
      component: StrategyDetail,
    },
    {
      path: '/account',
      name: 'Account',
      component: Account,
    },
    {
      path: '/backtest',
      name: 'Backtest',
      component: Backtest,
    },
  ],
})

export default router
