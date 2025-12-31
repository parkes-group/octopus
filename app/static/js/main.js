/**
 * Main JavaScript for Octopus Pricing Assistant
 * MVP: Basic form validation and interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        if (alert.classList.contains('alert-dismissible')) {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000);
        }
    });
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Duration input validation
    const durationInput = document.getElementById('duration');
    if (durationInput) {
        durationInput.addEventListener('input', function() {
            const value = parseFloat(this.value);
            if (value < 0.5 || value > 6.0) {
                this.setCustomValidity('Duration must be between 0.5 and 6 hours');
            } else {
                this.setCustomValidity('');
            }
        });
    }
    
    // Capacity input validation
    const capacityInput = document.getElementById('capacity');
    if (capacityInput) {
        capacityInput.addEventListener('input', function() {
            if (this.value) {
                const value = parseFloat(this.value);
                if (value < 0.1 || value > 100) {
                    this.setCustomValidity('Capacity must be between 0.1 and 100 kWh');
                } else {
                    this.setCustomValidity('');
                }
            } else {
                this.setCustomValidity('');
            }
        });
    }
});

