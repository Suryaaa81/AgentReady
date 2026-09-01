import { useState } from "react";
import { api } from "../lib/api";


export default function Chat() {
  const [messages, setMessages] = useState<{ role: string, content: string }[]>([
    { role: "assistant", content: "Hi! I'm the AgentReady Assistant. Ask me about products or create a checkout." }
  ]);
  const [input, setInput] = useState("");
  const [checkoutSession, setCheckoutSession] = useState<any>(null);

  const sendMessage = async () => {
    if (!input.trim()) return;
    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput("");

    try {
      const res = await api.chat(newMessages);
      // Show assistant reply
      setMessages(prev => [...prev, { role: "assistant", content: res.reply }]);

      // If tool_calls returned, display their results as system messages
      if (res.tool_calls && Array.isArray(res.tool_calls)) {
        for (const tc of res.tool_calls) {
          const content = `Tool: ${tc.name}\nResult: ${JSON.stringify(tc.result)}`;
          setMessages(prev => [...prev, { role: "assistant", content }]);
          // If tool result included a checkout, set it
          if (tc.name === "create_checkout" && tc.result && tc.result.checkout_id) {
            setCheckoutSession(tc.result);
          }
        }
      }
    } catch (e: any) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: Unable to process message (${e?.message || "connection error"}). Please check your API key or server status.`,
        },
      ]);
    }
  };

  const handleCheckout = async () => {
    if (!checkoutSession) return;
    try {
      await api.authorizeCheckout(checkoutSession.checkout_id || checkoutSession.id);
      const pay = await api.createPayment(checkoutSession.checkout_id || checkoutSession.id);
      // For test mode, backend verifies signature using configured secret; simulate by calling verify endpoint with dummy ids
      await api.verifyPayment({
        razorpay_order_id: pay.razorpay_order_id,
        razorpay_payment_id: "pay_simulated_success",
        razorpay_signature: "mock_sig_disabled"
      });
      alert("Payment successful!");
      setCheckoutSession(null);
    } catch (e: any) {
      alert("Checkout failed: " + e.message);
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <div className="w-1/2 max-w-lg mx-auto bg-white shadow-xl flex flex-col h-full">
        <header className="p-4 bg-blue-600 text-white font-bold text-lg">
          AgentReady Chat
        </header>
        
        <div className="flex-1 p-4 overflow-y-auto space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`p-3 rounded-lg max-w-[80%] ${m.role === "user" ? "bg-blue-100 self-end ml-auto" : "bg-gray-100"}`}>
              <div className="text-xs font-semibold mb-1 opacity-50 capitalize">{m.role}</div>
              <div className="whitespace-pre-wrap">{m.content}</div>
            </div>
          ))}
          
          {checkoutSession && checkoutSession.status === "READY" && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <h3 className="font-bold text-green-800">Checkout Available</h3>
              <p className="text-sm my-2">Total: ₹{checkoutSession.total_amount}</p>
              <button onClick={handleCheckout} className="bg-green-600 text-white px-4 py-2 rounded font-semibold w-full">
                Pay Now
              </button>
            </div>
          )}
        </div>

        <div className="p-4 bg-gray-50 flex gap-2">
          <input 
            value={input} 
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            className="flex-1 border rounded p-2"
            placeholder="Type your message..."
          />
          <button onClick={sendMessage} className="bg-blue-600 text-white px-4 py-2 rounded">Send</button>
        </div>
      </div>
    </div>
  );
}
