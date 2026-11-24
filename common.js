// common.js — Shared JS for all pages

(function () {
    function initCommon() {
        if (window.__siteCommonInitialized) return;
        window.__siteCommonInitialized = true;

        // --- Navbar: highlight current page ---
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(function (link) {
            const href = link.getAttribute('href');
            if (href === currentPage || (currentPage === '' && href === 'index.html')) {
                link.classList.add('active');
            }
        });

        // --- Navbar: mobile menu toggle & close behavior ---
        const navbarToggler = document.querySelector(".navbar-toggler");
        const navbarCollapse = document.querySelector(".navbar-collapse");

        if (navbarToggler && navbarCollapse) {
            const MENU_ICON_OPEN = '<line x1="4" y1="7" x2="20" y2="7" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="17" x2="20" y2="17" />';
            const MENU_ICON_CLOSE = '<line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" />';

            function setMenuState(isOpen) {
                navbarCollapse.classList.toggle("show", isOpen);
                navbarToggler.setAttribute("aria-expanded", String(isOpen));
                const icon = navbarToggler.querySelector("svg");
                if (icon) {
                    icon.innerHTML = isOpen ? MENU_ICON_CLOSE : MENU_ICON_OPEN;
                }
            }

            function closeMenu() {
                if (navbarCollapse.classList.contains("show")) {
                    setMenuState(false);
                }
            }

            navbarToggler.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                setMenuState(!navbarCollapse.classList.contains("show"));
            });

            navLinks.forEach(function (link) {
                link.addEventListener("click", closeMenu);
            });

            document.addEventListener("click", function (event) {
                const target = event.target;
                if (target instanceof Node && !navbarCollapse.contains(target) && !navbarToggler.contains(target)) {
                    closeMenu();
                }
            });

            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape") {
                    closeMenu();
                }
            });
        }

        // --- Popover: hover-text tooltips ---
        const popover = document.getElementById("popover");
        if (popover) {
            let hideTimeout;

            document.querySelectorAll(".hover-text").forEach(item => {
                item.addEventListener("mouseenter", function (event) {
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

                item.addEventListener("mouseleave", function () {
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
            window.addEventListener('scroll', function () {
                backBtn.classList.toggle('visible', window.scrollY > 300);
            });
            backBtn.addEventListener('click', function () {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initCommon);
    } else {
        initCommon();
    }
})();
