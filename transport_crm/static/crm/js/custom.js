// Анимация появления строк таблицы при загрузке
document.addEventListener("DOMContentLoaded", function() {
    const rows = document.querySelectorAll("tbody tr");
    rows.forEach((row, index) => {
        row.style.animation = `fadeInRow 0.4s ease ${index * 0.1}s both`;
    });

    // Всплывающая подсказка для кнопок действий (tooltips)
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Стиль анимации строк (добавляем через JS, чтобы не засорять CSS)
const styleSheet = document.createElement("style");
styleSheet.textContent = `
@keyframes fadeInRow {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}`;
document.head.appendChild(styleSheet);