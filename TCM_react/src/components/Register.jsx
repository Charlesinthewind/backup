import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  Link,
  InputAdornment,
  IconButton,
  Grid,
  CssBaseline
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';

const Register = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    email: ''
  });
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    try {
      const registrationData = {
        username: formData.username,
        password: formData.password,
      };
      
      if (formData.email.trim()) {
        registrationData.email = formData.email.trim();
      }

      const response = await fetch('http://localhost:8000/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registrationData),
      });

      const data = await response.json();

      if (response.ok) {
        navigate('/login');
      } else {
        setError(data.error || '注册失败');
      }
    } catch (error) {
      setError('网络错误，请稍后重试');
    }
  };

  const handleClickShowPassword = (field) => {
    if (field === 'password') {
      setShowPassword(!showPassword);
    } else {
      setShowConfirmPassword(!showConfirmPassword);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        backgroundColor: '#f5f5f5'
      }}
    >
      <CssBaseline />
      {/* 左侧介绍部分 */}
      <Box
        sx={{
          width: '35%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: '#1976d2',
          color: 'white',
          p: 4,
          my: 4, // 上下margin
          ml: 4, // 左侧margin
          borderRadius: 2, // 圆角
        }}
      >
        <Box
          component="img"
          src="/logo.svg"
          alt="Logo"
          sx={{
            width: 100,
            height: 100,
            mb: 4,
            filter: 'brightness(0) invert(1)'
          }}
        />
        <Typography variant="h3" component="h1" gutterBottom sx={{ fontSize: '2.5rem' }}>
          中医古籍知识图谱问答系统
        </Typography>
        <Typography variant="h6" sx={{ maxWidth: 400, textAlign: 'center', mb: 4, fontSize: '1.1rem' }}>
          基于知识图谱的中医古籍智能问答系统
        </Typography>
        <Typography variant="body1" sx={{ maxWidth: 400, textAlign: 'center', opacity: 0.8, fontSize: '0.95rem' }}>
          本系统整合了大量中医古籍知识，包括方剂、中药、症状等多维度信息，
          通过知识图谱技术，为用户提供准确的中医古籍知识查询和咨询服务。
        </Typography>
      </Box>

      {/* 右侧注册表单 */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: 4,
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 6,
            width: '100%',
            maxWidth: 480,
            borderRadius: 2,
            bgcolor: 'background.paper',
            boxShadow: '0 8px 24px rgba(0,0,0,0.1)'
          }}
        >
          <Typography variant="h4" component="h2" sx={{ mb: 4, textAlign: 'center', fontWeight: 500 }}>
            注册新账号
          </Typography>
          <Box component="form" onSubmit={handleSubmit} noValidate>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <TextField
                  required
                  fullWidth
                  id="username"
                  label="用户名"
                  name="username"
                  autoComplete="username"
                  value={formData.username}
                  onChange={handleChange}
                  autoFocus
                  InputProps={{
                    sx: { borderRadius: 1.5, fontSize: '1.1rem' }
                  }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  required
                  fullWidth
                  name="password"
                  label="密码"
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  autoComplete="new-password"
                  value={formData.password}
                  onChange={handleChange}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          aria-label="toggle password visibility"
                          onClick={() => handleClickShowPassword('password')}
                          edge="end"
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                    sx: { borderRadius: 1.5, fontSize: '1.1rem' }
                  }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  required
                  fullWidth
                  name="confirmPassword"
                  label="确认密码"
                  type={showConfirmPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  autoComplete="new-password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          aria-label="toggle password visibility"
                          onClick={() => handleClickShowPassword('confirm')}
                          edge="end"
                        >
                          {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                    sx: { borderRadius: 1.5, fontSize: '1.1rem' }
                  }}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  id="email"
                  label="邮箱（选填）"
                  name="email"
                  autoComplete="email"
                  value={formData.email}
                  onChange={handleChange}
                  type="email"
                  InputProps={{
                    sx: { borderRadius: 1.5, fontSize: '1.1rem' }
                  }}
                />
              </Grid>
            </Grid>
            {error && (
              <Typography color="error" variant="body2" sx={{ mt: 2 }}>
                {error}
              </Typography>
            )}
            <Button
              type="submit"
              fullWidth
              variant="contained"
              sx={{ 
                mt: 4, 
                mb: 3, 
                py: 1.8, 
                borderRadius: 2,
                fontSize: '1.1rem',
                textTransform: 'none',
                boxShadow: '0 4px 12px rgba(25,118,210,0.2)'
              }}
            >
              注册
            </Button>
            <Box sx={{ textAlign: 'center' }}>
              <Link
                href="/login"
                variant="body1"
                sx={{
                  textDecoration: 'none',
                  '&:hover': {
                    textDecoration: 'underline',
                  },
                  fontSize: '1rem',
                  color: 'primary.main'
                }}
              >
                {"已有账号？立即登录"}
              </Link>
            </Box>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default Register; 