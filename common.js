// common.js — Shared JS for all pages

document.addEventListener("DOMContentLoaded", function () {
    // --- Navbar: highlight current page ---
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const navLinks = document.querySelectorAll('.nav-link');
    navLinks.forEach(function(link) {
        const href = link.getAttribute('href');
        if (href === currentPage || (currentPage === '' && href === 'index.html')) {
            link.classList.add('active');
        }
    });

    // --- Navbar: mobile menu close behavior ---
    const navbarToggler = document.querySelector(".navbar-toggler");
    const navbarCollapse = document.querySelector(".navbar-collapse");

    navLinks.forEach(function (link) {
        link.addEventListener("click", function () {
            if (navbarCollapse.classList.contains("show")) {
                navbarToggler.click();
            }
        });
    });

    document.addEventListener("click", function (event) {
        if (!navbarCollapse.contains(event.target) && !navbarToggler.contains(event.target)) {
            navbarCollapse.classList.remove("show");
        }
    });

    navbarCollapse.addEventListener("mouseleave", function () {
        navbarCollapse.classList.remove("show");
    });

    // --- Popover: hover-text tooltips ---
    const popover = document.getElementById("popover");
    if (popover) {
        let hideTimeout;

        document.querySelectorAll(".hover-text").forEach(item => {
            item.addEventListener("mouseenter", function(event) {
                clearTimeout(hideTimeout);
                popover.textContent = this.getAttribute("data-text");
                popover.style.display = "block";
                popover.style.opacity = "1";

                let x = event.pageX;
                let y = event.pageY + 10;

                const popoverWidth = popover.offsetWidth;
                if (x + popoverWidth > window.innerWidth) {
                    x = window.innerWidth - popoverWidth - 10;
                }

                popover.style.left = x + "px";
                popover.style.top = y + "px";
            });

            item.addEventListener("mouseleave", function() {
                hideTimeout = setTimeout(() => {
                    popover.style.opacity = "0";
                    setTimeout(() => {
                        popover.style.display = "none";
                    }, 200);
                }, 300);
            });
        });

        popover.addEventListener("mouseenter", function () {
            clearTimeout(hideTimeout);
        });

        popover.addEventListener("mouseleave", function () {
            popover.style.opacity = "0";
            setTimeout(() => {
                popover.style.display = "none";
            }, 200);
        });
    }

    // --- Back-to-top button ---
    const backBtn = document.querySelector('.back-to-top');
    if (backBtn) {
        window.addEventListener('scroll', function() {
            backBtn.classList.toggle('visible', window.scrollY > 300);
        });
        backBtn.addEventListener('click', function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});
