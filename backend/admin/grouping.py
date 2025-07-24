# backend/admin/grouping.py - ПРОСТА НАВІГАЦІЯ
from django.contrib import admin
from backend.admin.admin_group_titles import GROUP_TITLES


def custom_get_app_list(self, request):
    app_dict = self._build_app_dict(request)
    group_dict = {}

    for app_name, app in app_dict.items():
        for model in app["models"]:
            object_name = model.get("object_name")
            if not object_name:
                continue
            label = GROUP_TITLES.get(object_name, "🔧 Інші")
            model["app_label"] = label
            group_dict.setdefault(label, []).append(model)

    # 🎯 ВАЖЛИВІ ГРУПИ ЗВЕРХУ
    priority_groups = [
        "🏢 Компанії та фірми",
        "📦 Товари та склад",
        "🧾 Документи та операції",
        "👥 Клієнти та постачальники",
        "💰 Ціни та знижки",
        "💵 Каса та банк",
        "🖨️ Касові апарати",
        "🏭 Виробництво",
        "👨‍💻 Користувачі та права",
        "⚙️ Налаштування",
        "📊 Логи системи",
        "🔧 Інші"
    ]

    result = []

    # Додаємо групи у порядку пріоритету
    for group_name in priority_groups:
        if group_name in group_dict:
            result.append({
                "name": group_name,
                "app_label": group_name,
                "models": sorted(group_dict[group_name], key=lambda x: x["name"]),
            })

    # Додаємо решту груп (якщо є)
    for group_name in sorted(group_dict.keys()):
        if group_name not in priority_groups:
            result.append({
                "name": group_name,
                "app_label": group_name,
                "models": sorted(group_dict[group_name], key=lambda x: x["name"]),
            })

    return result


def setup_custom_admin_ui():
    """Налаштування адмін панелі"""
    admin.AdminSite.get_app_list = custom_get_app_list

    # Покращені заголовки
    admin.site.index_title = "📊 Панель управління ERP"
    admin.site.site_header = "💼 NashSoft ERP - Адміністрування"
    admin.site.site_title = "NashSoft"