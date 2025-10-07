window.addEventListener('load', async function() {
  const chatkit = document.getElementById('chatkit-element');

  // Fetch client token from backend
  const response = await fetch('/api/chatkit/session', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });
  const { client_secret } = await response.json();

  chatkit.setOptions({
    api: {
      clientToken: client_secret
    },
    theme: {
      colorScheme: "auto",
      color: {
        accent: {
          primary: "#2D8CFF",
          level: 500
        }
      },
      radius: "round",
      density: "comfortable",
      typography: {
        fontFamily: "'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
      }
    },
    composer: {
      placeholder: "Ask me anything about your data...",
      allowFileAttachments: true
    },
    startScreen: {
      greeting: "👋 Hello! I'm your Analyst Agent",
      starterPrompts: [
        {
          label: "Analyze sales data",
          icon: "chart-bar",
          prompt: "Can you analyze the sales data and show me trends?"
        },
        {
          label: "Generate report",
          icon: "document-text",
          prompt: "Generate a summary report of recent activities"
        },
        {
          label: "Data insights",
          icon: "lightbulb",
          prompt: "What insights can you provide from my data?"
        }
      ]
    },
    header: {
      enabled: true
    }
  });
});
