import React, { useState, useEffect, useRef } from 'react';
import { Box, TextField, Button, Paper, Typography, List, ListItem, ListItemText, Container, IconButton, AppBar, Toolbar } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import KnowledgeGraph from './KnowledgeGraph';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';

const Chat = () => {
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [error, setError] = useState('');
  const [editingConversation, setEditingConversation] = useState(null);
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef(null);
  const navigate = useNavigate();
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const eventSourceRef = useRef(null);
  const [graphLinks, setGraphLinks] = useState({});

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    // 检查用户是否登录
    try {
      const userStr = localStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      if (!user) {
        navigate('/login');
        return;
      }
      fetchConversations();
    } catch (error) {
      console.error('Error checking user authentication:', error);
      navigate('/login');
    }
  }, [navigate]);

  useEffect(() => {
    if (currentConversation) {
      fetchMessages(currentConversation);
    }
  }, [currentConversation]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const fetchConversations = async () => {
    try {
      setLoading(true);
      setError('');
      
      const userStr = localStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      if (!user) {
        navigate('/login');
        return;
      }

      const response = await fetch(`http://localhost:8000/api/conversations?user_id=${user.id}`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '获取对话列表失败');
      }
      
      const data = await response.json();
      if (!Array.isArray(data)) {
        console.error('Conversations data is not an array:', data);
        setConversations([]);
        return;
      }
      
      setConversations(data);
      if (data.length > 0 && !currentConversation) {
        setCurrentConversation(data[0].id);
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
      setError(error.message || '获取对话列表失败');
      setConversations([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchMessages = async (conversationId) => {
    try {
      const response = await fetch(`http://localhost:8000/api/conversation/${conversationId}/messages`);
      const data = await response.json();
      setMessages(data);
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const createNewConversation = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user'));
      if (!user) {
        navigate('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/conversation', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: user.id }),
      });
      const data = await response.json();
      setCurrentConversation(data.conversation_id);
      
      // 发送欢迎消息
      const welcomeResponse = await fetch(`http://localhost:8000/api/conversation/${data.conversation_id}/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: "我是一名中医古籍小助手，有什么可以帮到您呢？",
          role: 'assistant',
        }),
      });

      if (!welcomeResponse.ok) {
        throw new Error('Failed to send welcome message');
      }

      // 重新获取对话列表和消息
      await fetchConversations();
      await fetchMessages(data.conversation_id);
    } catch (error) {
      console.error('Error creating new conversation:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !currentConversation) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    
    // 添加用户消息
    const newUserMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      setIsStreaming(true);
      setStreamingMessage('');
      
      // 添加系统消息占位
      const systemMessageId = Date.now() + 1;
      setMessages(prev => [...prev, {
        id: systemMessageId,
        role: 'system',
        content: '',
        timestamp: new Date().toISOString()
      }]);

      const response = await fetch('http://localhost:8000/api/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: userMessage,
          conversation_id: currentConversation
        })
      });

      if (!response.ok) {
        throw new Error('流式响应请求失败');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6));
              
              if (eventData.error) {
                setStreamingMessage(prev => prev + '\n' + eventData.error);
              } else if (eventData.content) {
                setStreamingMessage(prev => prev + eventData.content);
              } else if (eventData.finished) {
                setIsStreaming(false);
                // 在流结束后获取知识图谱数据
                fetchKnowledgeGraph(userMessage, systemMessageId);
              }
            } catch (e) {
              console.error('解析流数据出错:', e);
            }
          }
        }
      }
      
      setIsStreaming(false);
      
    } catch (error) {
      console.error('Error sending message:', error);
      setIsStreaming(false);
      setMessages(prev => prev.map(msg => 
        msg.content === '' && msg.role === 'system' 
          ? {...msg, content: '消息发送失败，请重试'} 
          : msg
      ));
    }
  };

  const fetchKnowledgeGraph = async (query, messageId) => {
    try {
      console.log('Requesting knowledge graph for:', {
        query,
        messageId,
        conversationId: currentConversation
      });

      const response = await fetch('http://localhost:8000/api/knowledge-graph', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          conversation_id: currentConversation,
          message_id: messageId
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('Knowledge Graph API Error:', {
          status: response.status,
          statusText: response.statusText,
          error: errorData
        });
        return;
      }
      
      const data = await response.json();
      console.log('Knowledge graph response:', data);

      // 确保图谱数据存在才添加链接
      if (data && data.nodes && data.nodes.length > 0) {
        console.log('Setting graph link for message:', messageId);
        setGraphLinks(prev => ({
          ...prev,
          [messageId]: `/graph/${currentConversation}/${messageId}`
        }));
      } else {
        console.log('No valid graph data received');
      }
    } catch (error) {
      console.error('Error in fetchKnowledgeGraph:', error);
    }
  };

  // 监听流式消息变化，更新最后一条系统消息
  useEffect(() => {
    if (streamingMessage && messages.length > 0) {
      setMessages(prev => {
        const newMessages = [...prev];
        // 找到最后一条系统消息并更新内容
        for (let i = newMessages.length - 1; i >= 0; i--) {
          if (newMessages[i].role === 'system') {
            newMessages[i] = {
              ...newMessages[i],
              content: streamingMessage
            };
            break;
          }
        }
        return newMessages;
      });
    }
  }, [streamingMessage]);

  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSendMessage();
    }
  };

  const handleDeleteConversation = async (conversationId, event) => {
    event.stopPropagation(); // 防止触发会话选择
    try {
      const response = await fetch(`http://localhost:8000/api/conversation/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to delete conversation');
      }
      
      // 如果删除的是当前会话，清空消息和图谱数据
      if (currentConversation === conversationId) {
        setMessages([]);
        setCurrentConversation(null);
      }
      // 重新获取会话列表
      fetchConversations();
    } catch (error) {
      console.error('Error deleting conversation:', error);
      alert('删除会话失败: ' + error.message);
    }
  };

  const handleRenameConversation = async (conversationId, event) => {
    event.stopPropagation(); // 防止触发会话选择
    try {
      const userStr = localStorage.getItem('user');
      const user = userStr ? JSON.parse(userStr) : null;
      if (!user) {
        navigate('/login');
        return;
      }

      if (!newName.trim()) {
        throw new Error('名称不能为空');
      }

      const response = await fetch(`http://localhost:8000/api/conversation/${conversationId}/rename`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          user_id: user.id,
          name: newName.trim()
        }),
        credentials: 'include'  // 包含cookies
      });
      
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('对话不存在');
        } else if (response.status === 403) {
          throw new Error('无权限修改此对话');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || '重命名失败');
      }
      
      // 重新获取会话列表
      await fetchConversations();
      // 重置编辑状态
      setEditingConversation(null);
      setNewName('');
    } catch (error) {
      console.error('Error renaming conversation:', error);
      setError(error.message || '重命名失败');
      // 显示错误消息给用户
      alert(error.message || '重命名失败，请重试');
    }
  };

  const startEditing = (conversation, event) => {
    event.stopPropagation();
    setEditingConversation(conversation.id);
    setNewName(conversation.name || conversation.first_message || `对话 ${conversation.id}`);
  };

  const cancelEditing = (event) => {
    event.stopPropagation();
    setEditingConversation(null);
    setNewName('');
  };

  const handleLogout = () => {
    localStorage.removeItem('user');
    navigate('/login');
  };

  const renderMessage = (message) => (
    <Box
      key={message.id}
      sx={{
        display: 'flex',
        justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
        mb: 2,
        position: 'relative',
      }}
    >
      <Paper
        sx={{
          p: 2,
          maxWidth: '80%',
          width: message.role === 'system' ? '80%' : 'auto',
          backgroundColor: message.role === 'user' ? 'primary.light' : 'grey.100',
          color: message.role === 'user' ? 'white' : 'text.primary',
          position: 'relative',
        }}
      >
        <Box sx={{ minHeight: message.role === 'system' ? '100px' : 'auto' }}>
          {message.role === 'user' ? (
            <Typography>{message.content}</Typography>
          ) : (
            <>
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({node, ...props}) => <Typography {...props} />,
                  a: ({node, ...props}) => <Typography component="a" color="primary" {...props} />,
                  h1: ({node, ...props}) => <Typography variant="h5" gutterBottom {...props} />,
                  h2: ({node, ...props}) => <Typography variant="h6" gutterBottom {...props} />,
                  h3: ({node, ...props}) => <Typography variant="subtitle1" gutterBottom {...props} />,
                  pre: ({node, ...props}) => <pre style={{margin: '16px 0'}} {...props} />,
                  code: ({node, inline, ...props}) => 
                    inline ? (
                      <code {...props} />
                    ) : (
                      <pre>
                        <code {...props} />
                      </pre>
                    )
                }}
              >
                {message.content}
              </ReactMarkdown>
              {graphLinks[message.id] && (
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                  <Link 
                    to={graphLinks[message.id]}
                    style={{ textDecoration: 'none' }}
                  >
                    <Button
                      variant="outlined"
                      size="small"
                      endIcon={<OpenInNewIcon />}
                      sx={{ color: 'primary.main' }}
                    >
                      查看知识图谱
                    </Button>
                  </Link>
                </Box>
              )}
            </>
          )}
        </Box>
        {isStreaming && message.role === 'system' && message.content === streamingMessage && (
          <Box sx={{ 
            position: 'absolute',
            right: 8,
            bottom: 8,
            display: 'inline-block'
          }}>
            <Typography 
              component="span" 
              sx={{ 
                display: 'inline-block',
                animation: 'blink 1s infinite',
                '@keyframes blink': {
                  '0%': { opacity: 0 },
                  '50%': { opacity: 1 },
                  '100%': { opacity: 0 }
                }
              }}
            >
              ▋
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static">
        <Container maxWidth="lg" sx={{ px: 2 }}>
          <Toolbar sx={{ justifyContent: 'space-between', px: 0 }}>
            <Typography variant="h6">
              中医古籍知识图谱问答系统
            </Typography>
            <IconButton color="inherit" onClick={handleLogout}>
              <LogoutIcon />
            </IconButton>
          </Toolbar>
        </Container>
      </AppBar>
      <Container maxWidth="xl" sx={{ flex: 1, py: 2, px: 2 }}>
        <Box sx={{ display: 'flex', height: '100%', gap: 2 }}>
        {/* Conversations Sidebar - 固定宽度 */}
        <Paper sx={{ width: 260, minWidth: 260, p: 2, overflowY: 'auto' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">对话列表</Typography>
            <IconButton onClick={createNewConversation} color="primary">
              <AddIcon />
            </IconButton>
          </Box>
          {loading ? (
            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Typography color="text.secondary">
                加载中...
              </Typography>
            </Box>
          ) : error ? (
            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Typography color="error">
                {error}
              </Typography>
              <Button
                variant="contained"
                onClick={fetchConversations}
                sx={{ mt: 2 }}
              >
                重试
              </Button>
            </Box>
          ) : conversations.length === 0 ? (
            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Typography color="text.secondary">
                还没有对话记录
              </Typography>
              <Button
                variant="contained"
                onClick={createNewConversation}
                sx={{ mt: 2 }}
                startIcon={<AddIcon />}
              >
                开始新对话
              </Button>
            </Box>
          ) : (
            <List>
              {conversations.map((conv) => (
                <ListItem
                  key={conv.id}
                  button
                  selected={currentConversation === conv.id}
                  onClick={() => {
                    setCurrentConversation(conv.id);
                  }}
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'stretch',
                    '& .MuiListItemText-root': {
                      flex: 1,
                      mr: 1
                    }
                  }}
                >
                  {editingConversation === conv.id ? (
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center',
                      width: '100%',
                      gap: 1
                    }}>
                      <TextField
                        size="small"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            handleRenameConversation(conv.id, e);
                          }
                        }}
                        autoFocus
                        fullWidth
                      />
                      <IconButton
                        size="small"
                        onClick={(e) => handleRenameConversation(conv.id, e)}
                        color="primary"
                      >
                        <CheckIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={cancelEditing}
                        color="error"
                      >
                        <CloseIcon />
                      </IconButton>
                    </Box>
                  ) : (
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center',
                      width: '100%',
                      gap: 1
                    }}>
                      <ListItemText
                        primary={conv.name || conv.first_message || `对话 ${conv.id}`}
                        secondary={new Date(conv.created_at).toLocaleString()}
                        primaryTypographyProps={{ noWrap: true }}
                      />
                      <IconButton
                        size="small"
                        onClick={(e) => startEditing(conv, e)}
                        sx={{ color: 'primary.main' }}
                      >
                        <EditIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => handleDeleteConversation(conv.id, e)}
                        sx={{ color: 'error.main' }}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Box>
                  )}
                </ListItem>
              ))}
            </List>
          )}
        </Paper>

        {/* Chat Area */}
        <Paper sx={{ flex: 1, p: 2, display: 'flex', flexDirection: 'column' }}>
          {error ? (
            <Box sx={{ textAlign: 'center', mt: 4 }}>
              <Typography color="error">{error}</Typography>
            </Box>
          ) : !currentConversation ? (
            <Box sx={{ 
              flex: 1, 
              display: 'flex', 
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center'
            }}>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                选择一个对话或开始新对话
              </Typography>
              <Button
                variant="contained"
                onClick={createNewConversation}
                startIcon={<AddIcon />}
              >
                开始新对话
              </Button>
            </Box>
          ) : (
            <>
              {/* Messages and Knowledge Graph Container */}
              <Box sx={{ 
                flex: 1, 
                display: 'flex', 
                flexDirection: 'column', 
                height: '100%',
                maxHeight: 'calc(100vh - 160px)',
                overflow: 'hidden'
              }}>
                {/* Messages */}
                <Box sx={{ 
                  flex: 1, 
                  overflowY: 'auto', 
                  mb: 2,
                  maxHeight: '100%',
                  scrollBehavior: 'smooth',
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  '&::-webkit-scrollbar': {
                    width: '8px',
                  },
                  '&::-webkit-scrollbar-track': {
                    background: '#f1f1f1',
                    borderRadius: '4px',
                  },
                  '&::-webkit-scrollbar-thumb': {
                    background: '#888',
                    borderRadius: '4px',
                    '&:hover': {
                      background: '#555',
                    },
                  },
                }}>
                  <Box sx={{ 
                    flex: 1,
                    minHeight: 0,
                    paddingRight: '8px',
                    display: 'flex',
                    flexDirection: 'column',
                  }}>
                    {messages.map(message => renderMessage(message))}
                    <div ref={messagesEndRef} style={{ height: '1px', marginBottom: '8px' }} />
                  </Box>
                </Box>
              </Box>

              {/* Input Area */}
              <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
                <TextField
                  fullWidth
                  multiline
                  maxRows={4}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="输入消息..."
                  variant="outlined"
                />
                <Button
                  variant="contained"
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isStreaming}
                  sx={{ minWidth: 100 }}
                  endIcon={isStreaming ? null : <SendIcon />}
                >
                  {isStreaming ? '生成中...' : '发送'}
                </Button>
              </Box>
            </>
          )}
        </Paper>
      </Box>
    </Container>
    </Box>
  );
};

export default Chat; 