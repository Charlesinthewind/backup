import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Paper, IconButton, Typography, Container } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import KnowledgeGraph from './KnowledgeGraph';

const GraphPage = () => {
  const { conversationId, messageId } = useParams();
  const navigate = useNavigate();
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchGraphData = async () => {
      try {
        setLoading(true);
        console.log('Fetching graph data for:', { conversationId, messageId });
        
        // Convert string IDs to numbers
        const numericConversationId = parseInt(conversationId, 10);
        const numericMessageId = parseInt(messageId, 10);

        if (isNaN(numericConversationId) || isNaN(numericMessageId)) {
          throw new Error('Invalid conversation or message ID');
        }

        // First fetch the original query for this message
        const messageResponse = await fetch(`http://localhost:8000/api/conversation/${numericConversationId}/messages`);
        if (!messageResponse.ok) {
          throw new Error('Failed to fetch message data');
        }
        const messages = await messageResponse.json();
        
        console.log('All messages:', messages);
        
        // Find the last user message and its corresponding assistant response
        let userQuery = null;
        for (let i = messages.length - 1; i >= 0; i--) {
          const msg = messages[i];
          if (msg.role === 'user') {
            userQuery = msg.content;
            break;
          }
        }

        if (!userQuery) {
          throw new Error('No user query found in this conversation');
        }

        console.log('Using query:', userQuery);

        // Now fetch the graph with the user's query
        const response = await fetch('http://localhost:8000/api/knowledge-graph', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            conversation_id: numericConversationId,
            message_id: messages[messages.length - 1].id, // Use the last message ID
            query: userQuery
          })
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          console.error('API Error Response:', {
            status: response.status,
            statusText: response.statusText,
            error: errorData
          });
          throw new Error(`获取知识图谱数据失败: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Received graph data:', data);
        
        if (!data || !data.nodes || data.nodes.length === 0) {
          throw new Error('没有找到相关的知识图谱数据');
        }
        setGraphData(data);
      } catch (err) {
        console.error('Error in fetchGraphData:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();
  }, [conversationId, messageId]);

  const handleBack = () => {
    navigate(-1);
  };

  if (loading) {
    return (
      <Container>
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography>加载中...</Typography>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container>
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography color="error">{error}</Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ 
        p: 2, 
        borderBottom: 1, 
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        gap: 2
      }}>
        <IconButton onClick={handleBack}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h6">知识图谱详情</Typography>
      </Box>
      
      <Box sx={{ flex: 1, p: 2 }}>
        <Paper sx={{ 
          height: '100%',
          overflow: 'hidden',
          boxSizing: 'border-box'
        }}>
          {graphData && <KnowledgeGraph graphData={graphData} />}
        </Paper>
      </Box>
    </Box>
  );
};

export default GraphPage; 