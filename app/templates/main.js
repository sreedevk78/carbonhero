// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Voice Input Functionality
    const startVoiceBtn = document.getElementById('startVoice');
    if (startVoiceBtn) {
        startVoiceBtn.addEventListener('click', function() {
            if ('webkitSpeechRecognition' in window) {
                const recognition = new webkitSpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;

                recognition.onstart = function() {
                    document.getElementById('voiceStatus').textContent = 'Listening...';
                    startVoiceBtn.classList.add('btn-danger');
                    startVoiceBtn.classList.remove('btn-outline-success');
                };

                recognition.onresult = function(event) {
                    const transcript = event.results[0][0].transcript;
                    document.getElementById('voiceTranscript').textContent = transcript;
                    document.getElementById('voiceTranscript').classList.remove('d-none');
                    document.getElementById('voiceInput').value = transcript;
                    document.getElementById('voiceForm').classList.remove('d-none');
                };

                recognition.onend = function() {
                    document.getElementById('voiceStatus').textContent = 'Click to start recording';
                    startVoiceBtn.classList.remove('btn-danger');
                    startVoiceBtn.classList.add('btn-outline-success');
                };

                recognition.start();
            } else {
                document.getElementById('voiceStatus').textContent =
                    'Speech recognition is not supported in this browser.';
            }
        });
    }

    // Animate elements on scroll
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.fade-in');
        elements.forEach(element => {
            const elementTop = element.getBoundingClientRect().top;
            const elementVisible = 150;
            if (elementTop < window.innerHeight - elementVisible) {
                element.classList.add('visible');
            }
        });
    };

    window.addEventListener('scroll', animateOnScroll);

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Progress bar animations
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const width = bar.style.width;
        bar.style.width = '0';
        setTimeout(() => {
            bar.style.width = width;
        }, 100);
    });

    // Custom file input
    const fileInputs = document.querySelectorAll('.custom-file-input');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const fileName = e.target.files[0].name;
            const label = e.target.nextElementSibling;
            label.textContent = fileName;
        });
    });
});
