// Digital Club - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Theme toggle
    const root = document.documentElement;
    const themeToggle = document.getElementById('theme-toggle');
    const themeLabel = themeToggle ? themeToggle.querySelector('.theme-label') : null;
    const themeIcon = themeToggle ? themeToggle.querySelector('i') : null;
    const prefersLight = window.matchMedia('(prefers-color-scheme: light)');

    function setTheme(theme, persist = true) {
        root.setAttribute('data-theme', theme);
        if (persist) {
            localStorage.setItem('theme', theme);
        }
        if (themeToggle) {
            const isLight = theme === 'light';
            themeToggle.setAttribute('aria-pressed', String(isLight));
            if (themeLabel) themeLabel.textContent = isLight ? 'Dark' : 'Light';
            if (themeIcon) themeIcon.className = isLight ? 'fas fa-moon' : 'fas fa-sun';
        }
        document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
    }

    const storedTheme = localStorage.getItem('theme');
    if (storedTheme === 'light' || storedTheme === 'dark') {
        setTheme(storedTheme, false);
    } else {
        setTheme('light', false);
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = root.getAttribute('data-theme') || 'dark';
            setTheme(current === 'light' ? 'dark' : 'light');
        });
    }

    prefersLight.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches ? 'light' : 'dark', false);
        }
    });

    // Initialize AOS (Animate On Scroll)
    AOS.init({
        duration: 1000,
        easing: 'ease-in-out',
        once: true,
        offset: 100
    });

    // Mobile Navigation Toggle (modern sidebar)
    const navToggle = document.getElementById('nav-toggle');
    const navMenu = document.getElementById('nav-menu');
    const body = document.body;

    // Body scroll lock utility
    function lockBodyScroll() {
        if (window.innerWidth <= 768) {
            const scrollY = window.scrollY;
            body.style.position = 'fixed';
            body.style.top = `-${scrollY}px`;
            body.style.width = '100%';
            body.classList.add('menu-open');
        }
    }

    function unlockBodyScroll() {
        if (body.classList.contains('menu-open')) {
            const scrollY = body.style.top;
            body.style.position = '';
            body.style.top = '';
            body.style.width = '';
            body.classList.remove('menu-open');
            if (scrollY) {
                window.scrollTo(0, parseInt(scrollY || '0') * -1);
            }
        }
    }

    function closeMobileMenu() {
        if (navMenu && navMenu.classList.contains('active')) {
            navMenu.classList.remove('active');
            if (navToggle) {
                navToggle.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            }
            unlockBodyScroll();
        }
    }

    function openMobileMenu() {
        if (navMenu && !navMenu.classList.contains('active')) {
            navMenu.classList.add('active');
            if (navToggle) {
                navToggle.classList.add('active');
                navToggle.setAttribute('aria-expanded', 'true');
            }
            lockBodyScroll();
        }
    }

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            if (navMenu.classList.contains('active')) {
                closeMobileMenu();
            } else {
                openMobileMenu();
            }
        });

        // Close button inside sidebar
        const navClose = document.getElementById('nav-close');
        if (navClose) {
            navClose.addEventListener('click', (e) => {
                e.stopPropagation();
                closeMobileMenu();
                if (navToggle) navToggle.focus();
            });
        }

        // Close mobile menu when clicking on backdrop (body::before)
        document.addEventListener('click', function(e) {
            if (body.classList.contains('menu-open') && navMenu.classList.contains('active')) {
                // Check if click is outside the menu
                if (!navMenu.contains(e.target) && !navToggle.contains(e.target)) {
                    closeMobileMenu();
                }
            }
        });

        // Close mobile menu when clicking on a link (but not dropdown toggles)
        const navLinks = document.querySelectorAll('.nav-link:not(.dropdown-toggle):not(.dropdown-toggle *), .dropdown-item');
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                // Small delay to allow navigation
                setTimeout(() => {
                    closeMobileMenu();
                }, 100);
            });
        });

        // Prevent dropdown toggles from closing the mobile menu
        const dropdownToggles = document.querySelectorAll('.nav-dropdown .dropdown-toggle');
        dropdownToggles.forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });

        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && navMenu.classList.contains('active')) {
                closeMobileMenu();
                if (navToggle) navToggle.focus();
            }
        });

        // Close menu on window resize if switching to desktop
        let resizeTimer;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                if (window.innerWidth > 768) {
                    closeMobileMenu();
                }
            }, 250);
        });
    }

    // Dropdown Navigation Functionality
    initializeDropdowns();

    // Typing Animation for Hero Title
    const heroTitle = document.querySelector('.hero-title');
    if (heroTitle) {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        
        let i = 0;
        const typeWriter = () => {
            if (i < text.length) {
                heroTitle.textContent += text.charAt(i);
                i++;
                setTimeout(typeWriter, 100);
            }
        };
        
        setTimeout(typeWriter, 1000);
    }

    // Particle Background Effect
    createParticleBackground();

    // Newsletter Form Handling
    const newsletterForms = document.querySelectorAll('.newsletter-form');
    newsletterForms.forEach(form => {
        form.addEventListener('submit', handleNewsletterSubmit);
    });

    // Smooth Scrolling for Anchor Links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Card Hover Effects
    const cards = document.querySelectorAll('.card, .news-card, .project-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-10px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Loading States for Forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<div class="loading"></div>';
                submitBtn.disabled = true;
                
                // Re-enable after 3 seconds (adjust based on your needs)
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 3000);
            }
        });
    });

    // Navbar Background Change on Scroll
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', function() {
            navbar.classList.toggle('scrolled', window.scrollY > 100);
        }, { passive: true });
    }

    // Glitch Effect for Special Elements
    const glitchElements = document.querySelectorAll('.glitch');
    glitchElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.animation = 'glitch 0.3s infinite';
        });
        
        element.addEventListener('mouseleave', function() {
            this.style.animation = 'glitch 2s infinite';
        });
    });
});

// Particle Background Function
function createParticleBackground() {
    const canvas = document.createElement('canvas');
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '-1';
    canvas.style.opacity = '0.1';
    
    // Respect reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
        return; // Skip heavy visual effects
    }

    document.body.appendChild(canvas);
    
    const ctx = canvas.getContext('2d');
    let particles = [];
    let particleRgb = '0, 255, 255';
    let lineRgb = '0, 255, 255';

    function refreshParticleColors() {
        const styles = getComputedStyle(document.documentElement);
        particleRgb = styles.getPropertyValue('--particle-color').trim() || particleRgb;
        lineRgb = styles.getPropertyValue('--particle-line').trim() || lineRgb;
    }
    
    function resizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.floor(window.innerWidth * dpr);
        canvas.height = Math.floor(window.innerHeight * dpr);
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    
    function createParticle() {
        return {
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            size: Math.random() * 2 + 1,
            opacity: Math.random() * 0.5 + 0.2
        };
    }
    
    function initParticles() {
        particles = [];
        for (let i = 0; i < 50; i++) {
            particles.push(createParticle());
        }
    }
    
    function updateParticles() {
        particles.forEach(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;
            
            if (particle.x < 0 || particle.x > canvas.width) particle.vx *= -1;
            if (particle.y < 0 || particle.y > canvas.height) particle.vy *= -1;
        });
    }
    
    function drawParticles() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        particles.forEach(particle => {
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${particleRgb}, ${particle.opacity})`;
            ctx.fill();
        });
        
        // Draw connections
        particles.forEach((particle, i) => {
            particles.slice(i + 1).forEach(otherParticle => {
                const distance = Math.sqrt(
                    Math.pow(particle.x - otherParticle.x, 2) +
                    Math.pow(particle.y - otherParticle.y, 2)
                );
                
                if (distance < 100) {
                    ctx.beginPath();
                    ctx.moveTo(particle.x, particle.y);
                    ctx.lineTo(otherParticle.x, otherParticle.y);
                    ctx.strokeStyle = `rgba(${lineRgb}, ${0.1 * (1 - distance / 100)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            });
        });
    }
    
    function animate() {
        updateParticles();
        drawParticles();
        requestAnimationFrame(animate);
    }
    
    refreshParticleColors();
    resizeCanvas();
    initParticles();
    animate();
    
    window.addEventListener('resize', () => {
        resizeCanvas();
        initParticles();
    });

    document.addEventListener('themechange', refreshParticleColors);
}

// Newsletter Form Handler
async function handleNewsletterSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalBtnContent = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.innerHTML = '<div class="loading"></div>';
    submitBtn.disabled = true;
    
    try {
        const response = await fetch('/newsletter/subscribe', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Successfully subscribed to newsletter!', 'success');
            form.reset();
        } else {
            showNotification(result.message, 'error');
        }
    } catch (error) {
        showNotification('An error occurred. Please try again.', 'error');
    } finally {
        // Restore button state
        submitBtn.innerHTML = originalBtnContent;
        submitBtn.disabled = false;
    }
}

// Notification System
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `flash-message flash-${type}`;
    notification.innerHTML = `
        <span>${message}</span>
        <button class="flash-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    flashContainer.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.body.appendChild(container);
    return container;
}

// Terminal-style typing effect
function typeWriter(element, text, speed = 50) {
    let i = 0;
    element.innerHTML = '';
    
    function type() {
        if (i < text.length) {
            element.innerHTML += text.charAt(i);
            i++;
            setTimeout(type, speed);
        }
    }
    
    type();
}

// Matrix rain effect (optional)
function createMatrixRain() {
    const canvas = document.createElement('canvas');
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '-2';
    canvas.style.opacity = '0.05';
    
    document.body.appendChild(canvas);
    
    const ctx = canvas.getContext('2d');
    const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
    const charArray = chars.split('');
    
    let fontSize = 14;
    let columns = 0;
    let drops = [];
    
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        columns = Math.floor(canvas.width / fontSize);
        drops = new Array(columns).fill(1);
    }
    
    function drawMatrix() {
        ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.fillStyle = '#00ff00';
        ctx.font = fontSize + 'px monospace';
        
        for (let i = 0; i < drops.length; i++) {
            const text = charArray[Math.floor(Math.random() * charArray.length)];
            ctx.fillText(text, i * fontSize, drops[i] * fontSize);
            
            if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }
    
    resizeCanvas();
    setInterval(drawMatrix, 50);
    
    window.addEventListener('resize', resizeCanvas);
}

// Initialize matrix rain on specific pages
if (window.location.pathname === '/' || window.location.pathname.includes('about')) {
    // Uncomment the line below to enable matrix rain effect
    // createMatrixRain();
}

// Utility Functions
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Dropdown Navigation Initialization
function initializeDropdowns() {
    const dropdowns = document.querySelectorAll('.nav-dropdown');
    const navMenu = document.getElementById('nav-menu');
    const navToggle = document.getElementById('nav-toggle');
    
    const canHover = window.matchMedia('(hover: hover)').matches;
    const isMobileViewport = () => window.innerWidth <= 768;

    function setDropdownHeight(menu, open) {
        if (!menu) return;
        if (open) {
            // Measure natural height for smooth accordion animation
            const height = menu.scrollHeight;
            menu.style.setProperty('--dropdown-height', `${height}px`);
            menu.style.maxHeight = `${height}px`;
        } else {
            menu.style.maxHeight = '0px';
            menu.style.setProperty('--dropdown-height', '0px');
        }
    }

    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.dropdown-toggle');
        const menu = dropdown.querySelector('.dropdown-menu');
        
        if (toggle && menu) {
            // Initialize ARIA attributes
            toggle.setAttribute('aria-haspopup', 'true');
            toggle.setAttribute('aria-expanded', 'false');
            menu.setAttribute('role', 'menu');

            // Desktop hover behavior only on hover-capable devices
            if (canHover) {
                let hoverTimeout;
                dropdown.addEventListener('mouseenter', () => {
                    clearTimeout(hoverTimeout);
                    dropdown.classList.add('active');
                    toggle.setAttribute('aria-expanded', 'true');
                });
                dropdown.addEventListener('mouseleave', () => {
                    hoverTimeout = setTimeout(() => {
                        dropdown.classList.remove('active');
                        toggle.setAttribute('aria-expanded', 'false');
                    }, 150);
                });
            }

            // Click behavior (mobile and desktop)
            toggle.addEventListener('click', (e) => {
                e.preventDefault();

                // Close other dropdowns
                dropdowns.forEach(otherDropdown => {
                    if (otherDropdown !== dropdown) {
                        otherDropdown.classList.remove('active');
                        const otherToggle = otherDropdown.querySelector('.dropdown-toggle');
                        if (otherToggle) otherToggle.setAttribute('aria-expanded', 'false');
                        if (isMobileViewport()) {
                            const otherMenu = otherDropdown.querySelector('.dropdown-menu');
                            setDropdownHeight(otherMenu, false);
                        }
                    }
                });

                // Toggle current dropdown
                const nowOpen = dropdown.classList.toggle('active');
                toggle.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
                if (isMobileViewport()) {
                    setDropdownHeight(menu, nowOpen);
                }
            });
            
            // Keyboard interactions for accessibility
            toggle.addEventListener('keydown', (e) => {
                const isOpen = dropdown.classList.contains('active');
                const items = Array.from(menu.querySelectorAll('.dropdown-item'));
                const firstItem = items[0];
                const lastItem = items[items.length - 1];

                switch (e.key) {
                    case 'Enter':
                    case ' ': // Space
                    case 'ArrowDown':
                        e.preventDefault();
                        if (!isOpen) {
                            dropdown.classList.add('active');
                            toggle.setAttribute('aria-expanded', 'true');
                        }
                        if (firstItem) firstItem.focus();
                        break;
                    case 'ArrowUp':
                        e.preventDefault();
                        if (!isOpen) {
                            dropdown.classList.add('active');
                            toggle.setAttribute('aria-expanded', 'true');
                        }
                        if (lastItem) lastItem.focus();
                        break;
                    default:
                        break;
                }
            });

            menu.addEventListener('keydown', (e) => {
                const items = Array.from(menu.querySelectorAll('.dropdown-item'));
                const currentIndex = items.indexOf(document.activeElement);
                if (e.key === 'Escape') {
                    dropdown.classList.remove('active');
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.focus();
                    if (isMobileViewport()) {
                        setDropdownHeight(menu, false);
                    }
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    const next = items[currentIndex + 1] || items[0];
                    if (next) next.focus();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    const prev = items[currentIndex - 1] || items[items.length - 1];
                    if (prev) prev.focus();
                } else if (e.key === 'Tab') {
                    // Close when tabbing out
                    if (!menu.contains(document.activeElement)) {
                        dropdown.classList.remove('active');
                        toggle.setAttribute('aria-expanded', 'false');
                    }
                }
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!dropdown.contains(e.target)) {
                    dropdown.classList.remove('active');
                    toggle.setAttribute('aria-expanded', 'false');
                    if (isMobileViewport()) {
                        setDropdownHeight(menu, false);
                    }
                }
            });
            
            // Close dropdown when clicking on dropdown items
            const dropdownItems = menu.querySelectorAll('.dropdown-item');
            dropdownItems.forEach(item => {
                item.setAttribute('role', 'menuitem');
                item.setAttribute('tabindex', '0');
                item.addEventListener('click', () => {
                    dropdown.classList.remove('active');
                    toggle.setAttribute('aria-expanded', 'false');
                    if (isMobileViewport()) {
                        setDropdownHeight(menu, false);
                    }
                });
            });
        }
    });
    
    // Close all dropdowns when window is resized
    window.addEventListener('resize', () => {
        dropdowns.forEach(dropdown => {
            dropdown.classList.remove('active');
            const t = dropdown.querySelector('.dropdown-toggle');
            if (t) t.setAttribute('aria-expanded', 'false');
            const menu = dropdown.querySelector('.dropdown-menu');
            setDropdownHeight(menu, false);
        });
    }, { passive: true });

    // Escape closes mobile nav
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (navMenu && navMenu.classList.contains('active')) {
                navMenu.classList.remove('active');
                if (navToggle) navToggle.classList.remove('active');
                if (navToggle) navToggle.focus();
            }
            document.querySelectorAll('.nav-dropdown.active').forEach(d => {
                d.classList.remove('active');
                const t = d.querySelector('.dropdown-toggle');
                if (t) t.setAttribute('aria-expanded', 'false');
            });
        }
    });
}

// Export functions for global use
window.DigitalClub = {
    showNotification,
    typeWriter,
    createParticleBackground,
    createMatrixRain,
    initializeDropdowns
};
