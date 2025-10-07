import { ChatKit, useChatKit } from '@openai/chatkit-react';
import './App.css';

function App() {
  const { control } = useChatKit({
    api: {
      url: '/chatkit',
      fetch(url, options = {}) {
        const { headers, ...rest } = options;
        const finalHeaders = new Headers(headers);
        const { body } = rest;

        if (body instanceof FormData) {
          finalHeaders.delete('Content-Type');
        } else if (!finalHeaders.has('Content-Type')) {
          finalHeaders.set('Content-Type', 'application/json');
        }

        return fetch(url, {
          ...rest,
          headers: finalHeaders,
        });
      },
      domainKey: 'http://localhost:8000',
      uploadStrategy: {
        type: 'direct',
        uploadUrl: 'http://localhost:8000/attachments/upload',
      },
    },
    composer: {
      attachments: {
        enabled: true,
      },
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
