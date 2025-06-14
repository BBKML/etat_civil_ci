function changeStatus(demandeId, newStatus) {
    if (confirm('Êtes-vous sûr de vouloir changer le statut?')) {
        // Logique AJAX pour changer le statut
        fetch(`/admin/change-status/${demandeId}/${newStatus}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Erreur lors du changement de statut');
            }
        });
    }
}

// Fonction pour obtenir le token CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Auto-refresh pour les demandes en temps réel
document.addEventListener('DOMContentLoaded', function() {
    // Refresh automatique toutes les 30 secondes pour la page des demandes
    if (window.location.pathname.includes('demandeacte')) {
        setInterval(() => {
            const currentTime = new Date().toLocaleTimeString();
            console.log(`Vérification des nouvelles demandes: ${currentTime}`);
            // Ici vous pouvez ajouter une logique pour vérifier les nouvelles demandes
        }, 30000);
    }
});

// Validation côté client pour les formulaires
document.addEventListener('DOMContentLoaded', function() {
    // Validation des numéros de téléphone ivoiriens
    const phoneInputs = document.querySelectorAll('input[name*="telephone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const phoneRegex = /^(\+225|0)[0-9]{8,10}$/;
            if (this.value && !phoneRegex.test(this.value)) {
                this.style.borderColor = '#dc3545';
                this.setCustomValidity('Format de téléphone ivoirien invalide');
            } else {
                this.style.borderColor = '#28a745';
                this.setCustomValidity('');
            }
        });
    });
});

// Notifications en temps réel (optionnel avec WebSocket)
class NotificationManager {
    constructor() {
        this.initializeNotifications();
    }
    
    initializeNotifications() {
        // Simulation de notifications
        setTimeout(() => {
            this.showNotification('Nouvelle demande reçue', 'info');
        }, 5000);
    }
    
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.style.position = 'fixed';
        notification.style.top = '70px';
        notification.style.right = '20px';
        notification.style.zIndex = '9999';
        notification.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}