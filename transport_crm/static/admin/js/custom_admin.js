document.addEventListener('DOMContentLoaded', function() {
    // Анимация появления строк таблиц
    const rows = document.querySelectorAll('#result_list tbody tr');
    rows.forEach((row, i) => {
        row.style.opacity = '0';
        row.style.transform = 'translateX(-10px)';
        setTimeout(() => {
            row.style.transition = 'all 0.3s ease';
            row.style.opacity = '1';
            row.style.transform = 'translateX(0)';
        }, i * 100);
    });

    // Анимация кнопок при наведении
    const buttons = document.querySelectorAll('input[type=submit], .button');
    buttons.forEach(btn => {
        btn.addEventListener('mouseenter', () => {
            btn.style.transform = 'translateY(-2px)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'translateY(0)';
        });
    });
});