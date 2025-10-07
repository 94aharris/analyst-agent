import { ChatKit, useChatKit } from '@openai/chatkit-react';
import './App.css';

function App() {
  const { control } = useChatKit({
    api: {
      url: '/chatkit',
      fetch(url, options) {
        return fetch(url, {
          ...options,
          headers: {
            ...options.headers,
            'Content-Type': 'application/json',
          },
        });
      },
      domainKey: 'http://localhost:8000',
    },
  });

  return (
    <div className="app">
      <h1>Analyst Agent</h1>
      <ChatKit control={control} className="chat-container" />
    </div>
  );
}

export default App;
