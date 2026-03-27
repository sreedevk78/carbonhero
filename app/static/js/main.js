// static/js/main.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })

    // Navbar shadow on scroll (matches .ch-navbar.is-scrolled in custom.css)
    var nav = document.querySelector('.ch-navbar')
    if (nav) {
        function updateNavScroll() {
            if (window.scrollY > 8) {
                nav.classList.add('is-scrolled')
            } else {
                nav.classList.remove('is-scrolled')
            }
        }
        updateNavScroll()
        window.addEventListener('scroll', updateNavScroll, { passive: true })
    }

    // Smooth scroll for same-page anchors (e.g. <a href="#section">) without breaking normal links
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var targetId = anchor.getAttribute('href')
            if (!targetId || targetId === '#') {
                return
            }
            var target = document.querySelector(targetId)
            if (target) {
                e.preventDefault()
                target.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }
        })
    })
});
