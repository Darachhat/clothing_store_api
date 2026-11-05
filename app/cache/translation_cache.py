"""Translation Cache Service.

High-performance cache layer for TRANSLATE_MODEL (base_data.translate).
Provides sub-millisecond Redis responses with in-memory fallback, bulk seed,
and cache invalidation.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_delete, redis_get, redis_set
from app.models.base_data_schema_model import TRANSLATE_MODEL


# Default seed catalog of admin UI content in 5 languages (en, km, cn, jp, kr)
ADMIN_FRONT_TRANSLATIONS: List[Dict[str, Any]] = [
    # ─── Navigation Sections ───────────────────────────────────────────────────
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "overview",
        "en": "Overview",
        "km": "ទិដ្ឋភាពទូទៅ",
        "cn": "概览",
        "jp": "概要",
        "kr": "개요",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "store",
        "en": "Store",
        "km": "ហាង",
        "cn": "门店",
        "jp": "店舗",
        "kr": "매장",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "catalog",
        "en": "Catalog",
        "km": "កាតាឡុក",
        "cn": "目录",
        "jp": "カタログ",
        "kr": "카탈로그",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "inventory",
        "en": "Inventory",
        "km": "សារពើភ័ណ្ឌ",
        "cn": "库存",
        "jp": "在庫",
        "kr": "재고",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "purchasing",
        "en": "Purchasing",
        "km": "ការទិញចូល",
        "cn": "采购",
        "jp": "仕入れ",
        "kr": "구매",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "customers",
        "en": "Customers",
        "km": "អតិថិជន",
        "cn": "客户",
        "jp": "顧客",
        "kr": "고객",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "finance",
        "en": "Finance",
        "km": "ហិរញ្ញវត្ថុ",
        "cn": "财务",
        "jp": "財務",
        "kr": "재무",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "reports",
        "en": "Reports",
        "km": "របាយការណ៍",
        "cn": "报表",
        "jp": "レポート",
        "kr": "보고서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav_section",
        "column_name": "administration",
        "en": "Administration",
        "km": "ការគ្រប់គ្រងប្រព័ន្ធ",
        "cn": "系统管理",
        "jp": "システム管理",
        "kr": "시스템 관리",
    },

    # ─── Navigation Items ─────────────────────────────────────────────────────
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "dashboard",
        "en": "Dashboard",
        "km": "ផ្ទាំងព័ត៌មាន",
        "cn": "仪表板",
        "jp": "ダッシュボード",
        "kr": "대시보드",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "pos_registers",
        "en": "POS Registers",
        "km": "ម៉ាស៊ីនគិតប្រាក់ POS",
        "cn": "收银机终端",
        "jp": "POSレジ端末",
        "kr": "POS 단말기",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "receipt_templates",
        "en": "Receipt Templates",
        "km": "គំរូវិក្កយបត្រ",
        "cn": "小票模板",
        "jp": "レシート雛形",
        "kr": "영수증 템플릿",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "sales_orders",
        "en": "Sales Orders",
        "km": "បញ្ជាទិញលក់",
        "cn": "销售订单",
        "jp": "販売注文",
        "kr": "판매 주문",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "returns",
        "en": "Returns",
        "km": "ការប្តូរ/សងទំនិញ",
        "cn": "退换货",
        "jp": "返品管理",
        "kr": "반품 관리",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "products",
        "en": "Products",
        "km": "ផលិតផល",
        "cn": "商品列表",
        "jp": "商品一覧",
        "kr": "상품 목록",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "categories",
        "en": "Categories",
        "km": "ប្រភេទផលិតផល",
        "cn": "商品分类",
        "jp": "カテゴリー",
        "kr": "카테고리",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "brands",
        "en": "Brands",
        "km": "ម៉ាកយីហោ",
        "cn": "品牌管理",
        "jp": "ブランド",
        "kr": "브랜드",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "print_labels",
        "en": "Print Labels",
        "km": "បោះពុម្ពស្លាកបាកូដ",
        "cn": "打印条码标签",
        "jp": "バーコードラベル印刷",
        "kr": "바코드 라벨 인쇄",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "stock_levels",
        "en": "Stock Levels",
        "km": "ចំនួនស្តុក",
        "cn": "库存余量",
        "jp": "在庫水準",
        "kr": "재고 현황",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "movements",
        "en": "Movements",
        "km": "បន្លាស់ទីស្តុក",
        "cn": "库存变动",
        "jp": "在庫移動履歴",
        "kr": "재고 변동 내역",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "transfers",
        "en": "Transfers",
        "km": "ផ្ទេរទំនិញ",
        "cn": "调拨管理",
        "jp": "在庫転送",
        "kr": "재고 이전",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "adjustments",
        "en": "Adjustments",
        "km": "ការកែតម្រូវស្តុក",
        "cn": "盘点调整",
        "jp": "在庫調整",
        "kr": "재고 조정",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "purchase_orders",
        "en": "Purchase Orders",
        "km": "ការបញ្ជាទិញទំនិញ",
        "cn": "采购订单",
        "jp": "発注書",
        "kr": "발주서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "suppliers",
        "en": "Suppliers",
        "km": "អ្នកផ្គត់ផ្គង់",
        "cn": "供应商",
        "jp": "仕入先",
        "kr": "공급업체",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "promotions",
        "en": "Promotions",
        "km": "ការបញ្ចុះតម្លៃ & ប្រូម៉ូសិន",
        "cn": "促销活动",
        "jp": "プロモーション",
        "kr": "프로모션",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "expenses",
        "en": "Expenses",
        "km": "ចំណាយប្រតិបត្តិការ",
        "cn": "费用支出",
        "jp": "経費管理",
        "kr": "지출 관리",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "sales_report",
        "en": "Sales Report",
        "km": "របាយការណ៍លក់",
        "cn": "销售报表",
        "jp": "売上レポート",
        "kr": "매출 보고서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "inventory_report",
        "en": "Inventory Report",
        "km": "របាយការណ៍ស្តុក",
        "cn": "库存报表",
        "jp": "在庫レポート",
        "kr": "재고 보고서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "purchases_report",
        "en": "Purchases Report",
        "km": "របាយការណ៍ទិញចូល",
        "cn": "采购报表",
        "jp": "仕入レポート",
        "kr": "구매 보고서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "profit_loss",
        "en": "Profit & Loss",
        "km": "ចំណេញ & ខាត",
        "cn": "损益表",
        "jp": "損益計算書",
        "kr": "손익 계산서",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "users",
        "en": "Users",
        "km": "អ្នកប្រើប្រាស់",
        "cn": "用户管理",
        "jp": "ユーザー管理",
        "kr": "사용자 관리",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "roles",
        "en": "Roles",
        "km": "តួនាទី & សិទ្ធិ",
        "cn": "角色权限",
        "jp": "役割と権限",
        "kr": "역할 및 권한",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "audit_logs",
        "en": "Audit Logs",
        "km": "កំណត់ហេតុសវនកម្ម",
        "cn": "审计日志",
        "jp": "監査ログ",
        "kr": "감사 로그",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "integrations",
        "en": "Integrations",
        "km": "ការតភ្ជាប់ប្រព័ន្ធ",
        "cn": "集成中心",
        "jp": "連携ハブ",
        "kr": "연동 허브",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "translations",
        "en": "Translations CMS",
        "km": "ការគ្រប់គ្រងខ្លឹមសារ & ភាសា",
        "cn": "多语言内容管理",
        "jp": "多言語コンテンツ管理",
        "kr": "다국어 콘텐츠 관리",
    },
    {
        "schema_name": "admin_front",
        "table_name": "nav",
        "column_name": "settings",
        "en": "Settings",
        "km": "ការកំណត់ហាង",
        "cn": "店铺设置",
        "jp": "店舗設定",
        "kr": "매장 설정",
    },

    # ─── Common Actions & UI Controls ─────────────────────────────────────────
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "save",
        "en": "Save",
        "km": "រក្សាទុក",
        "cn": "保存",
        "jp": "保存",
        "kr": "저장",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "cancel",
        "en": "Cancel",
        "km": "បោះបង់",
        "cn": "取消",
        "jp": "キャンセル",
        "kr": "취소",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "delete",
        "en": "Delete",
        "km": "លុប",
        "cn": "删除",
        "jp": "削除",
        "kr": "삭제",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "edit",
        "en": "Edit",
        "km": "កែប្រែ",
        "cn": "编辑",
        "jp": "編集",
        "kr": "수정",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "create",
        "en": "Create",
        "km": "បង្កើត",
        "cn": "新建",
        "jp": "新規作成",
        "kr": "생성",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "add",
        "en": "Add",
        "km": "បន្ថែម",
        "cn": "添加",
        "jp": "追加",
        "kr": "추가",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "search",
        "en": "Search...",
        "km": "ស្វែងរក...",
        "cn": "搜索...",
        "jp": "検索...",
        "kr": "검색...",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "filter",
        "en": "Filter",
        "km": "ចម្រោះ",
        "cn": "筛选",
        "jp": "絞り込み",
        "kr": "필터",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "reset",
        "en": "Reset",
        "km": "កំណត់ឡើងវិញ",
        "cn": "重置",
        "jp": "リセット",
        "kr": "재설정",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "refresh",
        "en": "Refresh",
        "km": "ផ្ទុកឡើងវិញ",
        "cn": "刷新",
        "jp": "更新",
        "kr": "새로고침",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "export_csv",
        "en": "Export CSV",
        "km": "ទាញយក CSV",
        "cn": "导出 CSV",
        "jp": "CSVエクスポート",
        "kr": "CSV 내보내기",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "print",
        "en": "Print",
        "km": "បោះពុម្ព",
        "cn": "打印",
        "jp": "印刷",
        "kr": "인쇄",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "close",
        "en": "Close",
        "km": "បិទ",
        "cn": "关闭",
        "jp": "閉じる",
        "kr": "닫기",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "confirm",
        "en": "Confirm",
        "km": "បញ្ជាក់",
        "cn": "确认",
        "jp": "確認",
        "kr": "확인",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "submit",
        "en": "Submit",
        "km": "ដាក់ស្នើ",
        "cn": "提交",
        "jp": "送信",
        "kr": "제출",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "back",
        "en": "Back",
        "km": "ថយក្រោយ",
        "cn": "返回",
        "jp": "戻る",
        "kr": "뒤로",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "actions",
        "en": "Actions",
        "km": "សកម្មភាព",
        "cn": "操作",
        "jp": "操作",
        "kr": "작업",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "status",
        "en": "Status",
        "km": "ស្ថានភាព",
        "cn": "状态",
        "jp": "状態",
        "kr": "상태",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "loading",
        "en": "Loading...",
        "km": "កំពុងដំណើរការ...",
        "cn": "加载中...",
        "jp": "読み込み中...",
        "kr": "로딩 중...",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "no_data",
        "en": "No data found",
        "km": "មិនមានទិន្នន័យទេ",
        "cn": "暂无数据",
        "jp": "データがありません",
        "kr": "데이터 없음",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "open_pos",
        "en": "Open POS",
        "km": "បើកម៉ាស៊ីន POS",
        "cn": "进入收银",
        "jp": "POSを開く",
        "kr": "POS 열기",
    },
    {
        "schema_name": "admin_front",
        "table_name": "common",
        "column_name": "language",
        "en": "Language",
        "km": "ភាសា",
        "cn": "语言",
        "jp": "言語",
        "kr": "언어",
    },

    # ─── Statuses ─────────────────────────────────────────────────────────────
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "active",
        "en": "Active",
        "km": "សកម្ម",
        "cn": "启用",
        "jp": "有効",
        "kr": "활성",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "inactive",
        "en": "Inactive",
        "km": "អសកម្ម",
        "cn": "停用",
        "jp": "無効",
        "kr": "비활성",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "draft",
        "en": "Draft",
        "km": "ព្រាង",
        "cn": "草稿",
        "jp": "下書き",
        "kr": "임시저장",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "completed",
        "en": "Completed",
        "km": "បានបញ្ចប់",
        "cn": "已完成",
        "jp": "完了",
        "kr": "완료",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "pending",
        "en": "Pending",
        "km": "រង់ចាំ",
        "cn": "待处理",
        "jp": "保留中",
        "kr": "대기 중",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "approved",
        "en": "Approved",
        "km": "បានអនុម័ត",
        "cn": "已批准",
        "jp": "承認済み",
        "kr": "승인됨",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "rejected",
        "en": "Rejected",
        "km": "បានបដិសេធ",
        "cn": "已拒绝",
        "jp": "却下",
        "kr": "거절됨",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "cancelled",
        "en": "Cancelled",
        "km": "បានបោះបង់",
        "cn": "已取消",
        "jp": "キャンセル済み",
        "kr": "취소됨",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "paid",
        "en": "Paid",
        "km": "បានទូទាត់",
        "cn": "已支付",
        "jp": "支払済み",
        "kr": "결제 완료",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "unpaid",
        "en": "Unpaid",
        "km": "មិនទាន់ទូទាត់",
        "cn": "未支付",
        "jp": "未払い",
        "kr": "미결제",
    },
    {
        "schema_name": "admin_front",
        "table_name": "status",
        "column_name": "refunded",
        "en": "Refunded",
        "km": "បានសងប្រាក់វិញ",
        "cn": "已退款",
        "jp": "返金済み",
        "kr": "환불됨",
    },

    # ─── Data Fields & Headers ────────────────────────────────────────────────
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "name",
        "en": "Name",
        "km": "ឈ្មោះ",
        "cn": "名称",
        "jp": "名称",
        "kr": "이름",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "sku",
        "en": "SKU",
        "km": "លេខកូដ SKU",
        "cn": "SKU码",
        "jp": "SKU",
        "kr": "SKU",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "barcode",
        "en": "Barcode",
        "km": "បាកូដ",
        "cn": "条形码",
        "jp": "バーコード",
        "kr": "바코드",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "price",
        "en": "Price",
        "km": "តម្លៃលក់",
        "cn": "售价",
        "jp": "販売価格",
        "kr": "가격",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "cost_price",
        "en": "Cost Price",
        "km": "តម្លៃដើម",
        "cn": "成本进价",
        "jp": "仕入原価",
        "kr": "원가",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "quantity",
        "en": "Quantity",
        "km": "បរិមាណ",
        "cn": "数量",
        "jp": "数量",
        "kr": "수량",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "total",
        "en": "Total",
        "km": "សរុប",
        "cn": "总计",
        "jp": "合計",
        "kr": "합계",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "subtotal",
        "en": "Subtotal",
        "km": "សរុបរង",
        "cn": "小计",
        "jp": "小計",
        "kr": "소계",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "discount",
        "en": "Discount",
        "km": "បញ្ចុះតម្លៃ",
        "cn": "折扣",
        "jp": "割引",
        "kr": "할인",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "tax",
        "en": "Tax",
        "km": "ពន្ធ",
        "cn": "税费",
        "jp": "消費税",
        "kr": "세금",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "date",
        "en": "Date",
        "km": "កាលបរិច្ឆេទ",
        "cn": "日期",
        "jp": "日付",
        "kr": "날짜",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "notes",
        "en": "Notes",
        "km": "កំណត់ចំណាំ",
        "cn": "备注",
        "jp": "備考",
        "kr": "비고",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "customer",
        "en": "Customer",
        "km": "អតិថិជន",
        "cn": "客户",
        "jp": "顧客",
        "kr": "고객",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "phone",
        "en": "Phone",
        "km": "លេខទូរស័ព្ទ",
        "cn": "电话",
        "jp": "電話番号",
        "kr": "전화번호",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "email",
        "en": "Email",
        "km": "អ៊ីមែល",
        "cn": "电子邮箱",
        "jp": "メールアドレス",
        "kr": "이메일",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "address",
        "en": "Address",
        "km": "អាសយដ្ឋាន",
        "cn": "地址",
        "jp": "住所",
        "kr": "주소",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "branch",
        "en": "Branch",
        "km": "សាខា",
        "cn": "分店",
        "jp": "支店",
        "kr": "지점",
    },
    {
        "schema_name": "admin_front",
        "table_name": "fields",
        "column_name": "warehouse",
        "en": "Warehouse",
        "km": "ឃ្លាំង",
        "cn": "仓库",
        "jp": "倉庫",
        "kr": "창고",
    },
]


class TranslationCacheService:
    """Redis-backed fast caching layer for TRANSLATE_MODEL."""

    CACHE_TTL: int = 3600  # 1 hour TTL
    KEY_PREFIX: str = "trans"

    @classmethod
    def _make_key(cls, schema_name: Optional[str], lang: Optional[str]) -> str:
        s = (schema_name or "all").lower().strip()
        l = (lang or "all").lower().strip()
        return f"{cls.KEY_PREFIX}:{s}:{l}"

    @classmethod
    async def get_translations(
        cls,
        db: AsyncSession,
        lang: Optional[str] = None,
        schema_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch translations from Redis cache; on miss, query database and populate cache."""
        cache_key = cls._make_key(schema_name, lang)

        # 1. Check Redis Cache
        cached = await redis_get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception as exc:
                logger.warning(f"[TRANSLATION_CACHE] JSON decode error for key {cache_key}: {exc}")

        # 2. Cache miss: Query DB
        stmt = select(TRANSLATE_MODEL).where(
            TRANSLATE_MODEL.status_code.in_(["ACTIVE", "active"]),
            TRANSLATE_MODEL.deleted_datetime.is_(None),
        )
        if schema_name and schema_name != "all":
            stmt = stmt.where(TRANSLATE_MODEL.schema_name == schema_name)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        # If DB is empty, auto-seed defaults
        if not rows:
            await cls.seed_translations(db)
            result = await db.execute(stmt)
            rows = result.scalars().all()

        # 3. Format output
        target_lang = (lang or "").lower().strip() if lang else None
        if target_lang in ("en", "km", "cn", "jp", "kr"):
            # Single language dictionary
            output: Dict[str, str] = {}
            for row in rows:
                key = f"{row.table_name}.{row.column_name}"
                val = getattr(row, target_lang, None) or row.en or ""
                output[key] = val
            data = {"locale": target_lang, "translations": output}
        else:
            # Multi-language dictionary
            multi: Dict[str, Dict[str, str]] = {
                "en": {},
                "km": {},
                "cn": {},
                "jp": {},
                "kr": {},
            }
            for row in rows:
                key = f"{row.table_name}.{row.column_name}"
                multi["en"][key] = row.en or ""
                multi["km"][key] = row.km or row.en or ""
                multi["cn"][key] = row.cn or row.en or ""
                multi["jp"][key] = row.jp or row.en or ""
                multi["kr"][key] = row.kr or row.en or ""
            data = {"locales": multi}

        # 4. Store in Redis
        try:
            await redis_set(cache_key, json.dumps(data), ex=cls.CACHE_TTL)
        except Exception as exc:
            logger.warning(f"[TRANSLATION_CACHE] Redis set error for {cache_key}: {exc}")

        return data

    @classmethod
    async def invalidate_cache(cls) -> None:
        """Clear cached translation keys."""
        try:
            for s in ("all", "admin_front", "ui", "common"):
                for l in ("all", "en", "km", "cn", "jp", "kr"):
                    await redis_delete(cls._make_key(s, l))
            logger.info("[TRANSLATION_CACHE] Cleared translation cache keys.")
        except Exception as exc:
            logger.warning(f"[TRANSLATION_CACHE] Invalidate error: {exc}")

    @classmethod
    async def seed_translations(cls, db: AsyncSession) -> int:
        """Upsert default translations into base_data.translate and warm cache."""
        inserted = 0
        for item in ADMIN_FRONT_TRANSLATIONS:
            stmt = select(TRANSLATE_MODEL).where(
                TRANSLATE_MODEL.schema_name == item["schema_name"],
                TRANSLATE_MODEL.table_name == item["table_name"],
                TRANSLATE_MODEL.column_name == item["column_name"],
                TRANSLATE_MODEL.deleted_datetime.is_(None),
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing:
                existing.en = item["en"]
                existing.km = item["km"]
                existing.cn = item["cn"]
                existing.jp = item["jp"]
                existing.kr = item["kr"]
                existing.status_code = "ACTIVE"
            else:
                record = TRANSLATE_MODEL(
                    id=uuid.uuid4(),
                    ref_id=uuid.uuid4(),
                    schema_name=item["schema_name"],
                    table_name=item["table_name"],
                    column_name=item["column_name"],
                    en=item["en"],
                    km=item["km"],
                    cn=item["cn"],
                    jp=item["jp"],
                    kr=item["kr"],
                    note="System UI seed translation",
                    status_code="ACTIVE",
                    created_by="system_seeder",
                )
                db.add(record)
                inserted += 1

        await db.commit()
        await cls.invalidate_cache()
        logger.info(f"[TRANSLATION_CACHE] Seeded {inserted} translations into base_data.translate.")
        return inserted


TRANSLATION_CACHE = TranslationCacheService

