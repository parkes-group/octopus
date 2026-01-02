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
    
    // Feature voting functionality
    initFeatureVoting();
});

/**
 * Initialize feature voting component.
 * Handles click voting with sessionStorage and displays percentage results.
 */
function initFeatureVoting() {
    const voteButtons = document.querySelectorAll('.feature-vote-btn');
    const voteMessage = document.querySelector('.feature-vote-message');
    const suggestionForm = document.querySelector('.feature-suggestion-form');
    const suggestionInput = document.querySelector('.feature-suggestion-input');
    const suggestionCharCount = document.querySelector('.suggestion-char-count');
    const suggestionMessage = document.querySelector('.feature-suggestion-message');
    
    // Check if user has already voted in this session
    const hasVoted = sessionStorage.getItem('feature_vote_recorded') === 'true';
    
    // Load and display current vote percentages
    loadVotePercentages();
    
    if (hasVoted) {
        // Disable all vote buttons if user has already voted
        voteButtons.forEach(btn => {
            btn.disabled = true;
            btn.classList.add('disabled');
            btn.setAttribute('aria-disabled', 'true');
        });
        
        // Show message if it exists
        if (voteMessage) {
            voteMessage.style.display = 'block';
        }
        
        // Show results for all features
        showVoteResults();
    } else {
        // Add click handlers to vote buttons
        voteButtons.forEach(button => {
            button.addEventListener('click', function() {
                const featureId = this.getAttribute('data-feature');
                
                if (!featureId) {
                    console.error('Feature ID not found');
                    return;
                }
                
                // Disable all buttons immediately to prevent double-clicking
                voteButtons.forEach(btn => {
                    btn.disabled = true;
                    btn.classList.add('disabled');
                    btn.setAttribute('aria-disabled', 'true');
                });
                
                // Show visual feedback on clicked button
                const checkIcon = this.querySelector('.feature-vote-check');
                if (checkIcon) {
                    checkIcon.style.display = 'inline';
                }
                this.classList.remove('btn-outline-primary');
                this.classList.add('btn-success');
                
                // Send vote to server
                fetch('/feature-vote', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        feature: featureId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Mark as voted in sessionStorage
                        sessionStorage.setItem('feature_vote_recorded', 'true');
                        
                        // Show success message
                        if (voteMessage) {
                            voteMessage.style.display = 'block';
                            voteMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        }
                        
                        // Update and display results
                        updateVoteResults(data.percentages);
                        showVoteResults();
                        
                        console.log('Vote recorded successfully:', data);
                    } else {
                        console.error('Error recording vote:', data.error);
                        // Re-enable buttons on error
                        voteButtons.forEach(btn => {
                            btn.disabled = false;
                            btn.classList.remove('disabled');
                            btn.removeAttribute('aria-disabled');
                        });
                        // Reset clicked button
                        this.classList.remove('btn-success');
                        this.classList.add('btn-outline-primary');
                        if (checkIcon) {
                            checkIcon.style.display = 'none';
                        }
                    }
                })
                .catch(error => {
                    console.error('Error sending vote:', error);
                    // Re-enable buttons on error
                    voteButtons.forEach(btn => {
                        btn.disabled = false;
                        btn.classList.remove('disabled');
                        btn.removeAttribute('aria-disabled');
                    });
                    // Reset clicked button
                    this.classList.remove('btn-success');
                    this.classList.add('btn-outline-primary');
                    if (checkIcon) {
                        checkIcon.style.display = 'none';
                    }
                });
            });
            
            // Add keyboard support (Enter and Space)
            button.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.click();
                }
            });
        });
    }
    
    // Character count for suggestion input
    if (suggestionInput && suggestionCharCount) {
        suggestionInput.addEventListener('input', function() {
            const length = this.value.length;
            suggestionCharCount.textContent = length;
            
            // Visual feedback for approaching limit
            if (length > 180) {
                suggestionCharCount.classList.add('text-danger');
            } else {
                suggestionCharCount.classList.remove('text-danger');
            }
        });
    }
    
    // Handle suggestion form submission
    if (suggestionForm && suggestionInput) {
        suggestionForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const suggestionText = suggestionInput.value.trim();
            
            if (!suggestionText) {
                suggestionInput.classList.add('is-invalid');
                return;
            }
            
            // Disable form during submission
            const submitBtn = this.querySelector('.feature-suggestion-submit');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Submitting...';
            }
            
            // Send suggestion to server
            fetch('/feature-suggestion', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    suggestion: suggestionText
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Clear input
                    suggestionInput.value = '';
                    suggestionCharCount.textContent = '0';
                    suggestionInput.classList.remove('is-invalid');
                    
                    // Show success message
                    if (suggestionMessage) {
                        suggestionMessage.style.display = 'block';
                        suggestionMessage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                    
                    console.log('Suggestion submitted successfully');
                } else {
                    console.error('Error submitting suggestion:', data.error);
                    suggestionInput.classList.add('is-invalid');
                }
            })
            .catch(error => {
                console.error('Error sending suggestion:', error);
                suggestionInput.classList.add('is-invalid');
            })
            .finally(() => {
                // Re-enable form
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit Suggestion';
                }
            });
        });
    }
}

/**
 * Load and display current vote percentages from server.
 */
function loadVotePercentages() {
    fetch('/feature-votes')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.percentages) {
                updateVoteResults(data.percentages);
                // Only show results if user has already voted
                if (sessionStorage.getItem('feature_vote_recorded') === 'true') {
                    showVoteResults();
                }
            }
        })
        .catch(error => {
            console.error('Error loading vote percentages:', error);
        });
}

/**
 * Update vote results display with percentages.
 */
function updateVoteResults(percentages) {
    const voteButtons = document.querySelectorAll('.feature-vote-btn');
    
    voteButtons.forEach(button => {
        const featureId = button.getAttribute('data-feature');
        const resultsDiv = button.querySelector('.feature-vote-results');
        const progressBar = button.querySelector('.progress-bar');
        const percentageSpan = button.querySelector('.feature-vote-percentage');
        
        if (resultsDiv && progressBar && percentageSpan && percentages[featureId]) {
            const percentage = percentages[featureId].percentage;
            progressBar.style.width = percentage + '%';
            progressBar.setAttribute('aria-valuenow', percentage);
            percentageSpan.textContent = percentage + '%';
        }
    });
}

/**
 * Show vote results for all features.
 */
function showVoteResults() {
    const resultsDivs = document.querySelectorAll('.feature-vote-results');
    resultsDivs.forEach(div => {
        div.style.display = 'block';
    });
}

