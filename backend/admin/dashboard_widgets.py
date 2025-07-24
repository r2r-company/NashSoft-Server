# backend/admin/dashboard_widgets.py - ШВИДКІ ДІЇ ТА ВІДЖЕТИ
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils.html import format_html
from django.db.models import Count, Sum
from datetime import datetime, timedelta


# Швидкі дії для адмінки
@staff_member_required
def quick_actions_view(request):
    """Сторінка швидких дій"""
    context = {
        'title': 'Швидкі дії',
        'actions': [
            {
                'name': 'Створити термінове замовлення',
                'description': 'Швидке створення виробничого замовлення',
                'url': '/admin/production/productionorder/add/?priority=urgent',
                'icon': '🚀'
            },
            {
                'name': 'Перевірити склад',
                'description': 'Швидкий огляд залишків на складі',
                'url': '/admin/backend/product/?o=1',
                'icon': '📦'
            },
            {
                'name': 'Створити документ приходу',
                'description': 'Оприбуткування товару',
                'url': '/admin/backend/document/add/?doc_type=receipt',
                'icon': '📄'
            },
            {
                'name': 'Додати нового клієнта',
                'description': 'Реєстрація нового контрагента',
                'url': '/admin/backend/customer/add/',
                'icon': '👤'
            }
        ]
    }
    return render(request, 'admin/quick_actions.html', context)


@staff_member_required
def dashboard_stats_view(request):
    """Статистика для дашборду"""
    today = datetime.now().date()

    try:
        # Імпортуємо моделі тільки коли потрібно
        from backend.models import Document, Product

        stats = {
            'documents_today': Document.objects.filter(date__date=today).count(),
            'total_products': Product.objects.count(),
            'recent_documents': Document.objects.order_by('-created_at')[:5]
        }

        # Якщо є модуль виробництва
        try:
            from production.models import ProductionOrder
            stats['production_orders_active'] = ProductionOrder.objects.filter(
                status__in=['planned', 'in_progress']
            ).count()
        except ImportError:
            stats['production_orders_active'] = 0

    except Exception as e:
        stats = {
            'error': f'Помилка завантаження статистики: {e}',
            'documents_today': 0,
            'total_products': 0,
            'production_orders_active': 0,
            'recent_documents': []
        }

    context = {
        'title': 'Статистика системи',
        'stats': stats
    }
    return render(request, 'admin/dashboard_stats.html', context)


# Додаткові URL для адмінки
def get_admin_urls():
    return [
        path('quick-actions/', quick_actions_view, name='quick_actions'),
        path('dashboard-stats/', dashboard_stats_view, name='dashboard_stats'),
    ]


# Розширення адмін панелі
class EnhancedAdminSite(admin.AdminSite):
    """Розширена адмін панель"""

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = get_admin_urls()
        return custom_urls + urls

    def index(self, request, extra_context=None):
        """Покращена головна сторінка"""
        if extra_context is None:
            extra_context = {}

        # Швидкі посилання
        quick_links = [
            {
                'title': '📦 Товари та склад',
                'links': [
                    {'name': 'Переглянути товари', 'url': '/admin/backend/product/'},
                    {'name': 'Додати товар', 'url': '/admin/backend/product/add/'},
                    {'name': 'Групи товарів', 'url': '/admin/backend/productgroup/'},
                ]
            },
            {
                'title': '🧾 Документи',
                'links': [
                    {'name': 'Всі документи', 'url': '/admin/backend/document/'},
                    {'name': 'Прихід товару', 'url': '/admin/backend/document/add/?doc_type=receipt'},
                    {'name': 'Продаж', 'url': '/admin/backend/document/add/?doc_type=sale'},
                ]
            },
            {
                'title': '🏭 Виробництво',
                'links': [
                    {'name': 'Виробничі замовлення', 'url': '/admin/production/productionorder/'},
                    {'name': 'Виробничі лінії', 'url': '/admin/production/productionline/'},
                    {'name': 'Плани виробництва', 'url': '/admin/production/productionplan/'},
                ]
            },
            {
                'title': '👥 Контрагенти',
                'links': [
                    {'name': 'Клієнти', 'url': '/admin/backend/customer/'},
                    {'name': 'Постачальники', 'url': '/admin/backend/supplier/'},
                    {'name': 'Додати клієнта', 'url': '/admin/backend/customer/add/'},
                ]
            }
        ]

        extra_context.update({
            'quick_links': quick_links,
            'show_quick_actions': True,
            'dashboard_title': 'Головна панель ERP системи'
        })

        return super().index(request, extra_context)


# Покращення існуючих моделей адмінки
def enhance_admin_models():
    """Додає корисні функції до існуючих моделей адмінки"""

    # Додаємо кольорові статуси для документів
    try:
        from backend.admin.document_admin import DocumentAdmin
        from backend.models import Document

        # Розширюємо функцію відображення статусу
        original_colored_status = DocumentAdmin.colored_status

        def enhanced_colored_status(self, obj):
            status_icons = {
                'draft': '📝',
                'posted': '✅',
                'cancelled': '❌'
            }
            icon = status_icons.get(obj.status, '❓')
            return format_html(
                '{} {}',
                icon,
                original_colored_status(self, obj)
            )

        DocumentAdmin.colored_status = enhanced_colored_status

    except ImportError:
        pass  # Якщо модель не знайдена


# HTML шаблони для швидких дій
QUICK_ACTIONS_TEMPLATE = """
{% extends "admin/base_site.html" %}
{% block content %}
<div class="dashboard">
    <h1>{{ title }}</h1>
    <div class="module">
        {% for action in actions %}
        <div style="margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
            <h3>{{ action.icon }} {{ action.name }}</h3>
            <p>{{ action.description }}</p>
            <a href="{{ action.url }}" class="button">Перейти</a>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""

DASHBOARD_STATS_TEMPLATE = """
{% extends "admin/base_site.html" %}
{% block content %}
<div class="dashboard">
    <h1>{{ title }}</h1>
    <div class="module">
        <h3>📊 Статистика за сьогодні</h3>
        <ul>
            <li>Документів створено: {{ stats.documents_today }}</li>
            <li>Загалом товарів: {{ stats.total_products }}</li>
            <li>Активних виробничих замовлень: {{ stats.production_orders_active }}</li>
        </ul>

        {% if stats.recent_documents %}
        <h3>📄 Останні документи</h3>
        <ul>
            {% for doc in stats.recent_documents %}
            <li>{{ doc.doc_number }} - {{ doc.get_doc_type_display }} ({{ doc.created_at|date:"H:i" }})</li>
            {% endfor %}
        </ul>
        {% endif %}
    </div>
</div>
{% endblock %}
"""