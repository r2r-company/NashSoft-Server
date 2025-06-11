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
            label = GROUP_TITLES.get(object_name, "Other")
            model["app_label"] = label
            group_dict.setdefault(label, []).append(model)

    return [
        {
            "name": group,               # 👈 Виводиться в сайдбар
            "app_label": group,          # 👈 для згортання
            "models": sorted(models, key=lambda x: x["name"]),
        }
        for group, models in sorted(group_dict.items())
    ]


def setup_custom_admin_ui():
    admin.AdminSite.get_app_list = custom_get_app_list
    admin.site.index_title = "📊 Панель керування"
    admin.site.site_header = "💼 Адмінка NashSoft"
    admin.site.site_title = "NashSoft"
