from pydantic import BaseModel


class PaymentCreate(BaseModel):
    checkout_id: str


class PaymentResponse(BaseModel):
    id: str
    razorpay_order_id: str
    amount: float
    currency: str
    status: str


class PaymentVerify(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
