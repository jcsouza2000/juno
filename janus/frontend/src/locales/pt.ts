// Português (pt-BR) — dicionário canônico. Todas as chaves devem existir aqui;
// en.ts e es.ts espelham esta estrutura. Use {var} para interpolação.

const pt = {
  lang: {
    pt: 'Português',
    en: 'Inglês',
    es: 'Espanhol',
    select: 'Idioma',
  },
  nav: {
    overview: 'Visão Geral',
    company: 'Minha Empresa',
    executiveKpis: 'KPIs Executivos',
    ai: 'IA Operacional',
    financial: 'Financeiro',
    myData: 'Meus Dados',
    integrations: 'Integrações ERP',
    audit: 'Auditoria',
    trust: 'Trust Center',
    users: 'Usuários',
    governance: 'Governança',
    autoTest: 'Auto Teste',
    demoExecutive: 'Demo Executivo',
    pilot: 'Piloto',
    systemStatus: 'Status Sistema',
    online: 'ONLINE',
  },
  header: {
    title: 'JUNO Industrial Diagnostic',
    signOut: 'Sair',
    noProfile: 'sem perfil',
    user: 'Usuário',
    hybridSaas: 'SaaS Híbrido',
  },
  common: {
    loading: 'Carregando...',
    loadingTenant: 'Carregando tenant ativo...',
    refresh: 'Atualizar',
    cancel: 'Cancelar',
    confirm: 'Confirmar',
    add: 'Adicionar',
    remove: 'Remover',
    delete: 'Excluir',
    save: 'Salvar',
    noCompany: 'Nenhuma empresa vinculada ao usuário.',
    activeCompany: 'Empresa ativa',
    empty: 'vazio',
    date: 'Data',
    rows: 'Linhas',
  },
  data: {
    title: 'Meus Dados',
    subtitle:
      'Tudo que está depositado no JUNO para a empresa ativa — e exclusão controlada sob comando do administrador.',
    totalRecords: 'Total de registros',
    periods: 'Períodos disponíveis ({count})',
    periodsColumn: 'Períodos',
    depositHistory: 'Histórico de depósitos',
    noDeposits: 'Nenhum depósito registrado.',
    origin: 'Origem',
    fileOrType: 'Arquivo / Tipo',
    group: {
      financial: 'Financeiro',
      erp: 'Operacional ERP',
      derived: 'KPIs derivados',
    },
    source: {
      financial: 'Financeiro',
      erp: 'ERP',
    },
    dangerZone: 'Zona de exclusão controlada',
    dangerIntro:
      'A exclusão remove apenas dados de negócio do tenant. Usuários, vínculos, conexões ERP e auditoria são preservados. A ação é irreversível.',
    scope: {
      financialTitle: 'Financeiro',
      financialDesc: 'DRE, Balanço, DFC e lançamentos. Também recalcula KPIs.',
      erpTitle: 'Operacional ERP',
      erpDesc: 'Produtos, clientes, fornecedores, pedidos e estoque.',
      allTitle: 'Tudo',
      allDesc: 'Todos os dados de negócio do tenant (mantém usuários e conexões).',
    },
    confirmLabel: 'Para confirmar, digite {token}',
    deleteButton: 'Excluir dados ({scope})',
    deleting: 'Excluindo...',
    deletedCount: '{count} registros excluídos (escopo: {scope})',
    confirmDialog:
      'Confirma a exclusão "{scope}" do tenant {company}? Esta ação é irreversível.',
    adminOnly: 'A exclusão de dados é restrita a administradores do tenant.',
  },
  users: {
    title: 'Usuários do Tenant',
    subtitle: 'Gerencie quem acessa {company} e o papel de cada um.',
    invite: 'Convidar usuário',
    emailPlaceholder: 'email@empresa.com',
    namePlaceholder: 'Nome completo (opcional)',
    addMember: 'Adicionar membro',
    adding: 'Adicionando...',
    members: 'Membros ({count})',
    noMembers: 'Nenhum membro neste tenant.',
    columnUser: 'Usuário',
    columnRole: 'Papel',
    columnJoined: 'Entrou em',
    columnActions: 'Ações',
    primary: 'Primário',
    tempPassword: 'Senha temporária:',
    tempPasswordNote:
      'Anote e repasse com segurança — esta senha não será exibida novamente.',
    createdNew: '(usuário novo)',
    createdExisting: '(usuário já existente)',
    addedAs: '{email} adicionado como {role}',
    removeConfirm: 'Remover {email} deste tenant? O usuário global é preservado.',
    ownerNote:
      'O último Proprietário não pode ser rebaixado nem removido. Remover um membro desfaz apenas o vínculo com este tenant — o usuário global é preservado.',
    role: {
      owner: 'Proprietário',
      admin: 'Administrador',
      member: 'Membro',
      viewer: 'Visualizador',
    },
  },
}

// O shape do PT é a fonte da verdade; en.ts e es.ts são validados contra ele.
export type Dictionary = typeof pt

export default pt
