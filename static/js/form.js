document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('ticketForm');
    const submitBtn = document.getElementById('submitBtn');
    const spinner = submitBtn.querySelector('.spinner-border');
    
    form.addEventListener('submit', function(e) {
        // Show loading state
        submitBtn.disabled = true;
        spinner.classList.remove('d-none');
        
        // Form validation
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const description = document.getElementById('description').value.trim();
        
        if (!name || !email || !description) {
            e.preventDefault();
            alert('Please fill in all required fields');
            submitBtn.disabled = false;
            spinner.classList.add('d-none');
            return false;
        }
        
        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            e.preventDefault();
            alert('Please enter a valid email address');
            submitBtn.disabled = false;
            spinner.classList.add('d-none');
            return false;
        }
        
        return true;
    });
});
