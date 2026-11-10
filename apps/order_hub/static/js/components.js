"""
Custom Web Components:
1. <order-summary-widget>: Encapsulated Shadow DOM element rendering order total calculation.
2. Async dynamic price estimators.
"""
class OrderSummaryWidget extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
    }

    static get observedAttributes() {
        return ['subtotal', 'discount', 'tax', 'shipping', 'total'];
    }

    attributeChangedCallback(name, oldValue, newValue) {
        this.render();
    }

    connectedCallback() {
        this.render();
    }

    render() {
        const subtotal = parseFloat(this.getAttribute('subtotal') || '0.00').toFixed(2);
        const discount = parseFloat(this.getAttribute('discount') || '0.00').toFixed(2);
        const tax = parseFloat(this.getAttribute('tax') || '0.00').toFixed(2);
        const shipping = parseFloat(this.getAttribute('shipping') || '0.00').toFixed(2);
        const total = parseFloat(this.getAttribute('total') || '0.00').toFixed(2);

        this.shadowRoot.innerHTML = `
            <style>
                :host {
                    display: block;
                    background: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 16px;
                    color: #f8fafc;
                    font-family: inherit;
                }
                .row {
                    display: flex;
                    justify-content: space-between;
                    font-size: 13px;
                    margin-bottom: 8px;
                    color: #94a3b8;
                }
                .row.total {
                    border-top: 1px solid #334155;
                    padding-top: 8px;
                    font-size: 15px;
                    font-weight: 700;
                    color: #38bdf8;
                }
                .discount-val { color: #34d399; }
            </style>
            <div>
                <div class="row"><span>Subtotal:</span><span id="shadow-subtotal">$${subtotal}</span></div>
                <div class="row"><span>Discount:</span><span id="shadow-discount" class="discount-val">-$${discount}</span></div>
                <div class="row"><span>Tax (8%):</span><span id="shadow-tax">$${tax}</span></div>
                <div class="row"><span>Shipping:</span><span id="shadow-shipping">$${shipping}</span></div>
                <div class="row total"><span>Final Total:</span><span id="shadow-total" data-testid="shadow-final-total">$${total}</span></div>
            </div>
        `;
    }
}

customElements.define('order-summary-widget', OrderSummaryWidget);
