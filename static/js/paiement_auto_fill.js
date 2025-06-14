document.addEventListener('DOMContentLoaded', function() {
    const demandeSelect = document.getElementById('id_demande');
    
    if (demandeSelect) {
        demandeSelect.addEventListener('change', function() {
            const demandeId = this.value;
            if (demandeId) {
                fetch(`/admin/get_tarif/?demande_id=${demandeId}`)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.error) {
                            document.getElementById('id_montant').value = data.montant;
                            document.getElementById('id_montant_timbres').value = data.timbre;
                            document.getElementById('id_montant_total').value = data.total;
                        }
                    });
            }
        });
    }
});