export const state = {
    allEvents: [],
    displayEvents: [], // Filtered/Sorted list
    dateEvents: [], // For Student Ticket Calendar

    // Global data cache
    allArtistNames: [],  // 演员名称列表（向后兼容）
    artists: [],         // 完整演员对象数组（用于订阅等功能）

    // Current Tab
    currentTab: 'tab-hlq',

    // Hulaquan List Sort Settings
    sortField: 'city',
    sortAsc: true,

    // Column Visibility (Load from Storage)
    visibleColumns: JSON.parse(localStorage.getItem('hlq_columns')) || {
        city: true,
        update: true,
        title: true,
        location: false, // Default hidden
        price: true,
        stock: true
    },

    // Filter Settings (Hulaquan List)
    filterCity: '',

    // Co-Cast Settings
    coCastCols: {
        index: true,
        others: true,
        location: true
    },
    // Co-Cast State
    lastCoCastResults: [],
    lastCoCastSource: '',
    lastCoCastCasts: [],
    coCastYearFilter: '',
    coCastDateSort: true, // true=Asc, false=Desc

    // Detail View State (Temporary)
    currentDetailEvent: null,
    currentDetailTickets: null,
    currentDetailShowYear: false,
    currentDetailHasCast: false,

    // Date View State (Temporary)
    currentDateTickets: [],
    currentDate: ''
};
