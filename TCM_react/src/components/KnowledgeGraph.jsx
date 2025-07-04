import React, { useState, useEffect, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Box, Paper, Typography, Divider, IconButton, Tooltip } from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

const KnowledgeGraph = ({ graphData }) => {
  const graphRef = useRef();
  const [zoom, setZoom] = useState(1);
  
  // 恢复到初始视图
  const resetGraph = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 30);
      setZoom(1);
    }
  };
  
  // 放大图表
  const zoomIn = () => {
    if (graphRef.current) {
      const newZoom = Math.min(zoom + 0.2, 2.5);
      setZoom(newZoom);
      graphRef.current.zoom(newZoom);
    }
  };
  
  // 缩小图表
  const zoomOut = () => {
    if (graphRef.current) {
      const newZoom = Math.max(zoom - 0.2, 0.5);
      setZoom(newZoom);
      graphRef.current.zoom(newZoom);
    }
  };

  useEffect(() => {
    // 初始化时自动适配到窗口大小
    if (graphRef.current && graphData) {
      // 确保所有节点都有初始坐标
      graphData.nodes.forEach(node => {
        if (!node.x) node.x = 0;
        if (!node.y) node.y = 0;
      });

      setTimeout(() => {
        graphRef.current.zoomToFit(400);
      }, 300);
    }
  }, [graphData]);

  // If no graph data is available
  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    return (
      <Paper sx={{ p: 2, mt: 2, backgroundColor: 'grey.100' }}>
        <Typography variant="body2" color="text.secondary">
          没有相关知识图谱数据
        </Typography>
      </Paper>
    );
  }

  // 自定义节点渲染函数，显示标签文字
  const nodeCanvasObject = (node, ctx, globalScale) => {
    const label = node.label;
    const fontSize = 3;  // 进一步减小字体大小
    const nodeR = 3;     // 保持大节点尺寸
    
    // 检查节点坐标是否有效
    if (typeof node.x !== 'number' || typeof node.y !== 'number' || 
        isNaN(node.x) || isNaN(node.y)) {
      return null;
    }
    
    // 绘制节点圆形
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI);
    
    try {
      // 为每个节点创建渐变效果
      const gradient = ctx.createRadialGradient(
        node.x, node.y, 0,
        node.x, node.y, nodeR
      );
      gradient.addColorStop(0, '#4CAF50');
      gradient.addColorStop(1, '#2E7D32');
      ctx.fillStyle = gradient;
    } catch (error) {
      // 如果渐变创建失败，使用纯色
      ctx.fillStyle = '#4CAF50';
    }
    
    ctx.fill();
    
    // 添加节点边框
    ctx.strokeStyle = '#1B5E20';
    ctx.lineWidth = 4/globalScale;  // 增加边框宽度以匹配大节点
    ctx.stroke();
    
    // 设置文字样式
    ctx.font = `${fontSize}px Sans-Serif`;  // 移除最小字体大小限制
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    const textY = node.y + nodeR + fontSize * 0.6;  // 保持较小的文字间距
    const textWidth = ctx.measureText(label).width;
    const padding = 2/globalScale;  // 减小文字背景的内边距
    
    // 绘制文字背景
    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
    ctx.fillRect(
      node.x - textWidth/2 - padding,
      textY - fontSize/2 - padding,
      textWidth + padding * 2,
      fontSize + padding * 2
    );
    
    // 绘制文字
    ctx.fillStyle = '#1B5E20';
    ctx.fillText(label, node.x, textY);
    
    return { x: node.x, y: node.y };
  };
  
  // 自定义连接线渲染函数，显示关系类型
  const linkCanvasObject = (link, ctx, globalScale) => {
    const start = link.source;
    const end = link.target;
    
    // 如果源或目标不是有效对象，则跳过
    if (!start.x || !end.x) return;
    
    // 首先绘制连接线
    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = '#999';
    
    // 设置虚线效果
    ctx.setLineDash([2, 1]);
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();
    
    // 绘制箭头
    const arrowLength = 3 / globalScale;
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const unitX = dx / dist;
    const unitY = dy / dist;
    
    const arrowX = end.x - unitX * arrowLength * 2;
    const arrowY = end.y - unitY * arrowLength * 2;
    
    const arrowAngle = Math.atan2(dy, dx);
    const arrowSize = arrowLength;
    
    // 绘制箭头
    ctx.beginPath();
    ctx.moveTo(arrowX, arrowY);
    ctx.lineTo(
      arrowX - arrowSize * Math.cos(arrowAngle - Math.PI / 6),
      arrowY - arrowSize * Math.sin(arrowAngle - Math.PI / 6)
    );
    ctx.lineTo(
      arrowX - arrowSize * Math.cos(arrowAngle + Math.PI / 6),
      arrowY - arrowSize * Math.sin(arrowAngle + Math.PI / 6)
    );
    ctx.closePath();
    ctx.fillStyle = '#999';
    ctx.fill();
    
    // 重置虚线设置，避免影响其他绘制
    ctx.setLineDash([]);
    
    // 计算连接线的中点位置
    const midX = start.x + (end.x - start.x) / 2;
    const midY = start.y + (end.y - start.y) / 2;
    
    // 设置文本样式
    const fontSize = 2;
    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 使用多次绘制来创建柔和的轮廓效果
    const offsets = [
      [-0.5, -0.5], [0.5, -0.5],
      [-0.5, 0.5], [0.5, 0.5]
    ];
    
    // 绘制白色轮廓
    ctx.fillStyle = 'white';
    offsets.forEach(([ox, oy]) => {
      ctx.fillText(link.label, midX + ox, midY + oy);
    });
    
    // 绘制主要文字
    ctx.fillStyle = '#000';
    ctx.fillText(link.label, midX, midY);
  };

  return (
    <Paper sx={{ 
      width: '100vw',
      height: '100vh',
      position: 'fixed',
      top: 0,
      left: 0,
      m: 0,
      p: 0,
      borderRadius: 0,
      overflow: 'hidden',
      boxSizing: 'border-box',
      bgcolor: '#f5f5f5'
    }}>
      <Box sx={{ 
        position: 'absolute',
        top: 16,
        right: 16,
        zIndex: 1000,
        display: 'flex',
        gap: 1,
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        p: 1,
        borderRadius: 1
      }}>
        <Tooltip title="放大">
          <IconButton onClick={zoomIn} size="small">
            <ZoomInIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="缩小">
          <IconButton onClick={zoomOut} size="small">
            <ZoomOutIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="重置视图">
          <IconButton onClick={resetGraph} size="small">
            <RestartAltIcon />
          </IconButton>
        </Tooltip>
      </Box>
      
      <Box sx={{ 
        height: '100vh',
        width: '100vw'
      }}>
        <ForceGraph2D
          ref={graphRef}
          graphData={graphData}
          nodeLabel={null}
          nodeRelSize={30}
          linkDirectionalArrowLength={0}
          linkDirectionalArrowRelPos={1}
          backgroundColor="#f5f5f5"
          cooldownTime={2000}
          d3AlphaDecay={0.01}
          d3VelocityDecay={0.3}
          width={window.innerWidth}
          height={window.innerHeight}
          onEngineStop={() => graphRef.current?.zoomToFit(400, 60)}
          nodeCanvasObject={nodeCanvasObject}
          linkCanvasObject={linkCanvasObject}
          linkWidth={2}
          warmupTicks={200}
          cooldownTicks={200}
          d3Force={(force) => {
            force('charge')
              .strength(-2000)
              .distanceMax(300);

            force('link')
              .distance(200)
              .strength(0.5);

            force('center')
              .strength(0.2)
              .x(window.innerWidth / 2)
              .y(window.innerHeight / 2);

            force('collision')
              .radius(50)
              .strength(1);
          }}
        />
      </Box>
    </Paper>
  );
};

export default KnowledgeGraph; 