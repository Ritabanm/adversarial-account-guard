// ==========================================
// STELLAR INVOICE - APPLICATION CORE LOGIC
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // State Store
    let lineItems = [];
    let itemIdCounter = 0;



    // Element Selectors
    const btnDownload = document.getElementById('btn-download');
    const btnPrint = document.getElementById('btn-print');
    const btnReset = document.getElementById('btn-reset');
    const btnAddItem = document.getElementById('btn-add-item');
    const itemsContainer = document.getElementById('items-container');
    
    const bankTrigger = document.getElementById('sender-bank-trigger');
    const bankContent = document.getElementById('sender-bank-content');
    
    // List of form inputs that map directly to preview text elements
    const syncFields = [
        { inputId: 'sender-name', previewId: 'preview-sender-name', placeholder: 'Your Business Name' },
        { inputId: 'sender-email', previewId: 'preview-sender-email', placeholder: 'your-email@business.com' },
        { inputId: 'sender-phone', previewId: 'preview-sender-phone', placeholder: '' },
        { inputId: 'sender-website', previewId: 'preview-sender-website', placeholder: '' },
        { inputId: 'sender-address', previewId: 'preview-sender-address', placeholder: '' },
        { inputId: 'sender-bank-name', previewId: 'preview-bank-name', placeholder: '' },
        { inputId: 'sender-routing-number', previewId: 'preview-routing-number', placeholder: '' },
        { inputId: 'sender-account-number', previewId: 'preview-account-number', placeholder: '' },
        { inputId: 'sender-payment-terms', previewId: 'preview-other-instructions', placeholder: '' },
        
        { inputId: 'client-name', previewId: 'preview-client-name', placeholder: 'Client Name / Company' },
        { inputId: 'client-email', previewId: 'preview-client-email', placeholder: 'client-email@company.com' },
        { inputId: 'client-phone', previewId: 'preview-client-phone', placeholder: '' },
        { inputId: 'client-tax-id', previewId: 'preview-client-tax-id', placeholder: '' },
        { inputId: 'client-address', previewId: 'preview-client-address', placeholder: '' },
        
        { inputId: 'invoice-number', previewId: 'preview-invoice-num', placeholder: 'INV-XXXX' },
        { inputId: 'invoice-date', previewId: 'preview-invoice-date', placeholder: 'YYYY-MM-DD' },
        { inputId: 'invoice-due-date', previewId: 'preview-invoice-due-date', placeholder: 'YYYY-MM-DD' },
        { inputId: 'invoice-notes', previewId: 'preview-notes', placeholder: 'No notes added.' }
    ];

    // Local Storage Keys
    const STORAGE_KEY_SENDER = 'stellar_invoice_sender_info';

    // List of Sender Input IDs (for auto-saving)
    const senderFieldIds = [
        'sender-name',
        'sender-email',
        'sender-phone',
        'sender-website',
        'sender-address',
        'sender-bank-name',
        'sender-routing-number',
        'sender-account-number',
        'sender-payment-terms'
    ];

    // ==========================================
    // INITIALIZATION & EVENT LISTENERS
    // ==========================================

    function init() {
        // 1. Set Default Dates (Issue date = today, Due date = today + 30 days)
        const today = new Date();
        const dueDate = new Date();
        dueDate.setDate(today.getDate() + 30);
        
        document.getElementById('invoice-date').value = formatDate(today);
        document.getElementById('invoice-due-date').value = formatDate(dueDate);

        // 2. Load Sender Info from Local Storage & Premium State
        loadSenderInfo();

        // 3. Setup input event listeners for dynamic syncing & auto-saving
        setupSyncListeners();

        // 4. Setup Bank Details Collapse toggle
        setupCollapsible();

        // 5. Add default line items (demonstration items to WOW the user on load)
        addSampleItems();

        // 6. Setup button handlers
        btnAddItem.addEventListener('click', () => addLineItem());
        btnDownload.addEventListener('click', downloadPDF);
        btnPrint.addEventListener('click', () => window.print());
        btnReset.addEventListener('click', resetForm);
        
        // Currency Selector & Math triggers
        document.getElementById('invoice-currency').addEventListener('change', calculateTotals);
        document.getElementById('invoice-tax').addEventListener('input', calculateTotals);
        document.getElementById('invoice-discount').addEventListener('input', calculateTotals);

        // Run initial calculations
        calculateTotals();
    }

    // Format Date helper (YYYY-MM-DD)
    function formatDate(date) {
        const d = new Date(date);
        let month = '' + (d.getMonth() + 1);
        let day = '' + d.getDate();
        const year = d.getFullYear();

        if (month.length < 2) month = '0' + month;
        if (day.length < 2) day = '0' + day;

        return [year, month, day].join('-');
    }

    // ==========================================
    // SYNCING & LOCAL STORAGE
    // ==========================================

    function setupSyncListeners() {
        syncFields.forEach(field => {
            const inputEl = document.getElementById(field.inputId);
            const previewEl = document.getElementById(field.previewId);
            
            if (inputEl && previewEl) {
                const updateHandler = () => {
                    const value = inputEl.value.trim();
                    
                    // Display text content or handle placeholders
                    if (value === '') {
                        previewEl.textContent = field.placeholder;
                        previewEl.classList.add('empty-field');
                    } else {
                        previewEl.textContent = value;
                        previewEl.classList.remove('empty-field');
                    }
                    
                    // Specific dynamic visibility triggers
                    handleSpecialVisibilityTriggers();
                    
                    // Auto-save sender info to local storage if it's a sender field
                    if (senderFieldIds.includes(field.inputId)) {
                        saveSenderInfo();
                    }
                };

                // Trigger sync on input
                inputEl.addEventListener('input', updateHandler);
                // Trigger sync immediately to handle defaults/storage values
                updateHandler();
            }
        });
    }

    function handleSpecialVisibilityTriggers() {
        // Toggle Bank Details block visibility in invoice paper preview
        const bankNameVal = document.getElementById('sender-bank-name').value.trim();
        const accNumVal = document.getElementById('sender-account-number').value.trim();
        const bankContainer = document.getElementById('preview-bank-container');
        
        if (bankNameVal !== '' || accNumVal !== '') {
            bankContainer.classList.remove('hidden');
        } else {
            bankContainer.classList.add('hidden');
        }

        // Handle Bank other instructions field visibility label
        const otherInstVal = document.getElementById('sender-payment-terms').value.trim();
        const lblOtherInstructions = document.getElementById('lbl-other-instructions');
        if (otherInstVal === '') {
            lblOtherInstructions.classList.add('hidden');
        } else {
            lblOtherInstructions.classList.remove('hidden');
        }
    }

    // Save sender state to localStorage
    function saveSenderInfo() {
        const senderData = {};
        senderFieldIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                senderData[id] = el.value;
            }
        });
        localStorage.setItem(STORAGE_KEY_SENDER, JSON.stringify(senderData));
    }

    // Load sender state from localStorage
    function loadSenderInfo() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY_SENDER);
            if (stored) {
                const data = JSON.parse(stored);
                senderFieldIds.forEach(id => {
                    const el = document.getElementById(id);
                    if (el && data[id] !== undefined) {
                        el.value = data[id];
                    }
                });
            }
        } catch (e) {
            console.error('Error reading localStorage data:', e);
        }
    }



    // ==========================================
    // COLLAPSIBLE LOGIC (BANK DETAILS)
    // ==========================================

    function setupCollapsible() {
        bankTrigger.addEventListener('click', () => {
            const isCollapsed = bankContent.classList.contains('collapsed');
            const arrow = bankTrigger.querySelector('.arrow-icon');
            
            if (isCollapsed) {
                bankContent.classList.remove('collapsed');
                arrow.style.transform = 'rotate(180deg)';
            } else {
                bankContent.classList.add('collapsed');
                arrow.style.transform = 'rotate(0deg)';
            }
        });
    }

    // ==========================================
    // LINE ITEMS ENGINE
    // ==========================================

    function addLineItem(desc = '', qty = 1, rate = 0) {
        const id = ++itemIdCounter;
        const itemObj = { id, description: desc, quantity: qty, rate: rate };
        lineItems.push(itemObj);

        // Render input elements in left panel form
        const itemRowEl = document.createElement('div');
        itemRowEl.className = 'item-row';
        itemRowEl.id = `item-row-${id}`;
        
        itemRowEl.innerHTML = `
            <div class="form-group mb-0">
                <input type="text" class="item-desc" placeholder="e.g. Design Consulting" value="${desc}">
            </div>
            <div class="form-group mb-0">
                <input type="number" class="item-qty" min="0" step="any" placeholder="1" value="${qty}">
            </div>
            <div class="form-group mb-0">
                <input type="number" class="item-rate" min="0" step="0.01" placeholder="0.00" value="${rate}">
            </div>
            <button type="button" class="btn-delete-row" title="Delete item">
                <svg class="icon-sm" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                </svg>
            </button>
        `;

        itemsContainer.appendChild(itemRowEl);

        // Add event listeners to input changes
        const inputDesc = itemRowEl.querySelector('.item-desc');
        const inputQty = itemRowEl.querySelector('.item-qty');
        const inputRate = itemRowEl.querySelector('.item-rate');
        const btnDelete = itemRowEl.querySelector('.btn-delete-row');

        inputDesc.addEventListener('input', (e) => {
            itemObj.description = e.target.value;
            renderPreviewTable();
        });

        inputQty.addEventListener('input', (e) => {
            itemObj.quantity = parseFloat(e.target.value) || 0;
            renderPreviewTable();
            calculateTotals();
        });

        inputRate.addEventListener('input', (e) => {
            itemObj.rate = parseFloat(e.target.value) || 0;
            renderPreviewTable();
            calculateTotals();
        });

        btnDelete.addEventListener('click', () => {
            removeItem(id);
        });

        // Trigger updates
        renderPreviewTable();
        calculateTotals();
    }

    function removeItem(id) {
        lineItems = lineItems.filter(item => item.id !== id);
        const rowEl = document.getElementById(`item-row-${id}`);
        if (rowEl) {
            rowEl.classList.add('removing');
            rowEl.addEventListener('animationend', () => rowEl.remove());
            // Fallback if animation is disabled
            setTimeout(() => rowEl.remove(), 150);
        }
        renderPreviewTable();
        calculateTotals();
    }

    function renderPreviewTable() {
        const previewBody = document.getElementById('preview-items-body');
        const currencySym = document.getElementById('invoice-currency').value;
        
        if (lineItems.length === 0) {
            previewBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center empty-table-msg">No items added yet.</td>
                </tr>
            `;
            return;
        }

        previewBody.innerHTML = '';
        lineItems.forEach(item => {
            const tr = document.createElement('tr');
            
            const total = item.quantity * item.rate;
            const descText = item.description.trim() === '' ? 'Item Description' : item.description;
            const descClass = item.description.trim() === '' ? 'empty-field' : '';

            tr.innerHTML = `
                <td class="${descClass}">${escapeHtml(descText)}</td>
                <td class="text-right">${item.quantity}</td>
                <td class="text-right">${currencySym}${item.rate.toFixed(2)}</td>
                <td class="text-right"><strong>${currencySym}${total.toFixed(2)}</strong></td>
            `;
            previewBody.appendChild(tr);
        });
    }

    // Simple HTML escaping helper to prevent script injection in preview
    function escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    // ==========================================
    // TOTALS CALCULATIONS
    // ==========================================

    function calculateTotals() {
        const currencySym = document.getElementById('invoice-currency').value;
        const taxRate = parseFloat(document.getElementById('invoice-tax').value) || 0;
        const discountRate = parseFloat(document.getElementById('invoice-discount').value) || 0;
        
        // Calculate Subtotal
        let subtotal = 0;
        lineItems.forEach(item => {
            subtotal += item.quantity * item.rate;
        });

        // Calculate Discount
        const discountAmount = subtotal * (discountRate / 100);
        const subtotalAfterDiscount = subtotal - discountAmount;

        // Calculate Tax
        const taxAmount = subtotalAfterDiscount * (taxRate / 100);

        // Calculate Grand Total
        const grandTotal = subtotalAfterDiscount + taxAmount;

        // Update DOM
        document.getElementById('preview-subtotal').textContent = `${currencySym}${subtotal.toFixed(2)}`;

        // Tax row handling
        const rowTax = document.getElementById('preview-row-tax');
        if (taxRate > 0) {
            rowTax.classList.remove('hidden');
            document.getElementById('preview-label-tax').textContent = `Tax (${taxRate}%)`;
            document.getElementById('preview-tax-amount').textContent = `+${currencySym}${taxAmount.toFixed(2)}`;
        } else {
            rowTax.classList.add('hidden');
        }

        // Discount row handling
        const rowDiscount = document.getElementById('preview-row-discount');
        if (discountRate > 0) {
            rowDiscount.classList.remove('hidden');
            document.getElementById('preview-label-discount').textContent = `Discount (-${discountRate}%)`;
            document.getElementById('preview-discount-amount').textContent = `-${currencySym}${discountAmount.toFixed(2)}`;
        } else {
            rowDiscount.classList.add('hidden');
        }

        // Grand Total Update
        document.getElementById('preview-total-due').textContent = `${currencySym}${grandTotal.toFixed(2)}`;
    }

    // ==========================================
    // PDF GENERATION (HTML2PDF.JS)
    // ==========================================

    function downloadPDF() {
        const element = document.getElementById('invoice-pdf-container');
        const invoiceNum = document.getElementById('invoice-number').value.trim() || 'draft';
        const clientName = document.getElementById('client-name').value.trim() || 'client';
        const cleanClientName = clientName.toLowerCase().replace(/[^a-z0-9]/g, '_');
        
        // Configuration options
        const opt = {
            margin:       0,
            filename:     `invoice_${invoiceNum}_${cleanClientName}.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { 
                scale: 2, 
                useCORS: true,
                letterRendering: true,
                scrollY: 0,
                scrollX: 0
            },
            jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
        };

        // Temporary styling optimization for perfect rendering during extraction
        const btnText = btnDownload.innerHTML;
        btnDownload.disabled = true;
        btnDownload.innerHTML = `
            <svg class="icon animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Generating PDF...
        `;

        // Style inject spin keyframe if it doesn't exist
        if (!document.getElementById('spin-style')) {
            const style = document.createElement('style');
            style.id = 'spin-style';
            style.innerHTML = `
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .animate-spin { animation: spin 1s linear infinite; }
                .opacity-25 { opacity: 0.25; }
                .opacity-75 { opacity: 0.75; }
            `;
            document.head.appendChild(style);
        }

        // Run pdf engine
        html2pdf().from(element).set(opt).save()
            .then(() => {
                btnDownload.disabled = false;
                btnDownload.innerHTML = btnText;
            })
            .catch(err => {
                console.error('PDF Generation failed:', err);
                alert('Could not generate PDF. Please try using the browser Print button and choosing "Save as PDF".');
                btnDownload.disabled = false;
                btnDownload.innerHTML = btnText;
            });
    }

    // ==========================================
    // UTILITY: DEMONSTRATION & RESET
    // ==========================================

    function addSampleItems() {
        // Default demonstration items so the user starts with a mock invoice
        addLineItem('Professional Web Application Design (Figma Wireframes & Prototype)', 1, 1200);
        addLineItem('Frontend Component Development (React/CSS Integration)', 40, 65);
        addLineItem('Deployment & Automated CI/CD Setup', 1, 450);
        
        // Pre-populate some client metadata for aesthetic visuals
        document.getElementById('client-name').value = 'Stark Industries';
        document.getElementById('client-email').value = 'billing@stark.com';
        document.getElementById('client-address').value = '10880 Malibu Point\nMalibu, CA 90265';
        document.getElementById('invoice-number').value = 'INV-2026-042';
        document.getElementById('invoice-tax').value = '8.25';
        document.getElementById('invoice-discount').value = '10';
        document.getElementById('invoice-notes').value = 'Thank you for your business! Payment is due net 30 via wire transfer. Use Invoice #INV-2026-042 as the reference note.';
        
        // Sync everything manually once
        syncFields.forEach(field => {
            const input = document.getElementById(field.inputId);
            if (input) {
                const event = new Event('input');
                input.dispatchEvent(event);
            }
        });
    }

    function resetForm() {
        if (confirm('Are you sure you want to clear the client info, invoice numbers, and all line items? (Your sender info is safe)')) {
            // Reset Client Info
            document.getElementById('client-name').value = '';
            document.getElementById('client-email').value = '';
            document.getElementById('client-phone').value = '';
            document.getElementById('client-tax-id').value = '';
            document.getElementById('client-address').value = '';

            // Reset Invoice Meta
            const today = new Date();
            const dueDate = new Date();
            dueDate.setDate(today.getDate() + 30);
            document.getElementById('invoice-date').value = formatDate(today);
            document.getElementById('invoice-due-date').value = formatDate(dueDate);
            document.getElementById('invoice-number').value = '';

            // Reset Line Items
            itemsContainer.innerHTML = '';
            lineItems = [];

            // Reset Financials & Notes
            document.getElementById('invoice-tax').value = '0';
            document.getElementById('invoice-discount').value = '0';
            document.getElementById('invoice-notes').value = '';

            // Sync everything
            syncFields.forEach(field => {
                const input = document.getElementById(field.inputId);
                if (input) {
                    const event = new Event('input');
                    input.dispatchEvent(event);
                }
            });

            calculateTotals();
        }
    }

    // Run startup
    init();
});
