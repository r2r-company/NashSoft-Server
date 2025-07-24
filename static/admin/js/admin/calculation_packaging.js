// static/admin/js/calculation_packaging.js
// ФІЛЬТРАЦІЯ ФАСУВАНЬ ЗА ОБРАНИМ ТОВАРОМ

document.addEventListener('DOMContentLoaded', function() {

    function filterPackagingOptions(componentSelect, packagingSelect) {
        const selectedProductId = componentSelect.value;

        if (!selectedProductId) {
            // Якщо товар не обрано - очищуємо фасування
            packagingSelect.innerHTML = '<option value="">---------</option>';
            return;
        }

        // Запит на сервер для отримання фасувань товару
        fetch(`/api/products/${selectedProductId}/packaging/`)
            .then(response => response.json())
            .then(data => {
                // Очищуємо список
                packagingSelect.innerHTML = '<option value="">Базова одиниця</option>';

                // Додаємо фасування
                data.packagings.forEach(packaging => {
                    const option = document.createElement('option');
                    option.value = packaging.id;
                    option.textContent = `${packaging.to_unit__name} (1 = ${packaging.factor} ${packaging.from_unit__name})`;
                    packagingSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Помилка завантаження фасувань:', error);
                packagingSelect.innerHTML = '<option value="">Помилка завантаження</option>';
            });
    }

    // Обробляємо всі рядки в inline формі
    function setupPackagingFilters() {
        const inlineRows = document.querySelectorAll('.dynamic-form');

        inlineRows.forEach(row => {
            const componentSelect = row.querySelector('select[name$="component"]');
            const packagingSelect = row.querySelector('select[name$="unit_conversion"]');

            if (componentSelect && packagingSelect) {
                // При зміні товару - оновлюємо фасування
                componentSelect.addEventListener('change', function() {
                    filterPackagingOptions(componentSelect, packagingSelect);
                });

                // Ініціалізуємо при завантаженні
                if (componentSelect.value) {
                    filterPackagingOptions(componentSelect, packagingSelect);
                }
            }
        });
    }

    // Запускаємо при завантаженні
    setupPackagingFilters();

    // Запускаємо при додаванні нових рядків
    const addRowButtons = document.querySelectorAll('.add-row a');
    addRowButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Даємо час на створення нового рядка
            setTimeout(setupPackagingFilters, 100);
        });
    });
});