import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import HealthView from '../views/HealthView.vue'
import HealthHistoryView from '../views/HealthHistoryView.vue'
import HealthDatabaseView from '../views/HealthDatabaseView.vue'
import FaultDatabaseView from '../views/FaultDatabaseView.vue'
import AlertsView from '../views/AlertsView.vue'
import BackendDemoShell from '../views/demo/BackendDemoShell.vue'
import DemoMonitorView from '../views/demo/MonitorView.vue'
import DemoSenderView from '../views/demo/SenderView.vue'
import DemoHealthDashboardView from '../views/demo/HealthDashboard.vue'
import FaultHistoryView from '../views/demo/FaultHistoryView.vue'
import IPSettingIndustrialView from '../views/IPSettingIndustrialView.vue'
import HealthAlgorithmCenterView from '../views/HealthAlgorithmCenterView.vue'
import RadarReconstructionView from '../views/RadarReconstructionView.vue'
import DataProcessingView from '../views/DataProcessingView.vue'
import FaultDiagnosisView from '../views/FaultDiagnosisView.vue'
import FaultHistoryCenterView from '../views/FaultHistoryCenterView.vue'
import SystemSelfCheckView from '../views/SystemSelfCheckView.vue'
import StatusMonitorView from '../views/StatusMonitorView.vue'
import UserManagementView from '../views/UserManagementView.vue'
import DiagnosisQueryView from '../views/DiagnosisQueryView.vue'
import SystemExtensionView from '../views/SystemExtensionView.vue'
import SubsystemDetailView from '../views/SubsystemDetailView.vue'
import BearingDiagnosisView from '../views/BearingDiagnosisView.vue'

const routes = [
  { path: '/', redirect: '/health' },
  { path: '/health', name: 'health', component: HealthView },
  { path: '/health-history', name: 'health-history', component: HealthHistoryView },
  { path: '/health-database', name: 'health-database', component: HealthDatabaseView },
  { path: '/fault-database', name: 'fault-database', component: FaultDatabaseView },
  { path: '/alerts', name: 'alerts', component: AlertsView },
  { path: '/health-algorithm', name: 'health-algorithm', component: HealthAlgorithmCenterView },
  { path: '/radar-reconstruction', name: 'radar-reconstruction', component: RadarReconstructionView },
  { path: '/data-processing', name: 'data-processing', component: DataProcessingView },
  { path: '/fault-diagnosis', name: 'fault-diagnosis', component: FaultDiagnosisView },
  { path: '/bearing-diagnosis', name: 'bearing-diagnosis', component: BearingDiagnosisView },
  { path: '/fault-history', name: 'fault-history', component: FaultHistoryCenterView },
  { path: '/system-self-check', name: 'system-self-check', component: SystemSelfCheckView },
  { path: '/status-monitor', name: 'status-monitor', component: StatusMonitorView },
  { path: '/user-management', name: 'user-management', component: UserManagementView },
  { path: '/diagnosis-query', name: 'diagnosis-query', component: DiagnosisQueryView },
  { path: '/system-extension', name: 'system-extension', component: SystemExtensionView },
  { path: '/subsystem/:id', name: 'subsystem-detail', component: SubsystemDetailView },
  {
    path: '/demo',
    component: BackendDemoShell,
    children: [
      { path: '', redirect: '/demo/monitor' },
      { path: 'monitor', name: 'demo-monitor', component: DemoMonitorView },
      { path: 'send', name: 'demo-send', component: DemoSenderView },
      { path: 'ip', name: 'demo-ip', component: IPSettingIndustrialView },
      {
        path: 'health-dashboard',
        name: 'demo-health-dashboard',
        component: DemoHealthDashboardView
      },
      {
        path: 'fault-history',
        name: 'demo-fault-history',
        component: FaultHistoryView
      }
    ]
  }
]

const isFileProtocol = typeof window !== 'undefined' && window.location.protocol === 'file:'

const router = createRouter({
  history: isFileProtocol ? createWebHashHistory() : createWebHistory(),
  routes
})

export default router
