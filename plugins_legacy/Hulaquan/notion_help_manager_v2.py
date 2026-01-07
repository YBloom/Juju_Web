#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notion 帮助文档管理器 V2
使用 Toggle 块实现美观的折叠/展开效果
"""

import json
from ncatbot.utils.logger import get_log

log = get_log()


class NotionHelpManager:
    """Notion 帮助文档管理器"""
    
    def __init__(self):
        """初始化管理器"""
        self.page_id = None
        self.public_url = None
        self.last_sync = None
    
    @staticmethod
    def generate_notion_blocks(help_sections, version_info):
        """
        生成 Notion 页面的 block 结构（使用 Toggle 实现折叠/展开）
        
        Args:
            help_sections: 帮助文档分类列表
            version_info: 版本信息字典 {version, bot_version, update_date}
        
        Returns:
            list: Notion blocks 列表
        """
        blocks = []
        
        # 标题 - 使用颜色强调
        blocks.append({
            "object": "block",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"📖 呼啦圈学生票机器人 - 帮助文档 {version_info['version']}"}
                }],
                "color": "blue"
            }
        })
        
        # 版本信息卡片（使用 callout）
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "ℹ️"},
                "color": "blue_background",
                "rich_text": [
                    {"type": "text", "text": {"content": f"🤖 Bot版本：{version_info['bot_version']}  |  "}},
                    {"type": "text", "text": {"content": f"📅 更新时间：{version_info['update_date']}  |  "}},
                    {"type": "text", "text": {"content": "💡 点击命令标题可展开查看详情"}}
                ]
            }
        })
        
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        
        # 遍历所有分类
        for section in help_sections:
            # 分类标题（Heading 2）
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": section['title']}
                    }],
                    "color": "default"
                }
            })
            
            for cmd in section['commands']:
                # 使用 Toggle 块实现折叠/展开
                # Toggle 标题：命令用法
                toggle_title = [
                    {"type": "text", "text": {"content": cmd['usage']}, "annotations": {"bold": True, "code": True}}
                ]
                
                # 添加别名到标题
                if 'aliases' in cmd:
                    toggle_title.append({
                        "type": "text", 
                        "text": {"content": f"  {' '.join(cmd['aliases'])}"},
                        "annotations": {"italic": True}
                    })
                
                # Toggle 内容：详细说明
                toggle_children = []
                
                # 功能描述（使用 quote）
                toggle_children.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": [
                            {"type": "text", "text": {"content": "💡 "}},
                            {"type": "text", "text": {"content": cmd['description']}}
                        ],
                        "color": "default"
                    }
                })
                
                # 变体用法
                if 'variants' in cmd:
                    toggle_children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "📝 格式："}, "annotations": {"bold": True}}]
                        }
                    })
                    for variant in cmd['variants']:
                        toggle_children.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": variant},
                                    "annotations": {"code": True}
                                }],
                                "color": "gray_background"
                            }
                        })
                
                # 参数说明
                if 'params' in cmd:
                    toggle_children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "🔧 参数："}, "annotations": {"bold": True}}]
                        }
                    })
                    for param, desc in cmd['params'].items():
                        toggle_children.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": f"{param}"}, "annotations": {"code": True, "bold": True}},
                                    {"type": "text", "text": {"content": f"：{desc}"}}
                                ]
                            }
                        })
                
                # 模式说明
                if 'modes' in cmd:
                    toggle_children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "⚙️ 模式："}, "annotations": {"bold": True}}]
                        }
                    })
                    for mode, desc in cmd['modes'].items():
                        toggle_children.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [
                                    {"type": "text", "text": {"content": f"{mode}"}, "annotations": {"code": True, "bold": True}},
                                    {"type": "text", "text": {"content": f"：{desc}"}}
                                ],
                                "color": "blue_background"
                            }
                        })
                
                # 示例
                if 'examples' in cmd:
                    toggle_children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "✨ 示例："}, "annotations": {"bold": True}}]
                        }
                    })
                    for example in cmd['examples']:
                        toggle_children.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": example},
                                    "annotations": {"code": True}
                                }],
                                "color": "green_background"
                            }
                        })
                
                # 注意事项
                if 'notes' in cmd:
                    toggle_children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": "⚠️ 注意："}, "annotations": {"bold": True}}]
                        }
                    })
                    for note in cmd['notes']:
                        toggle_children.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": note}
                                }],
                                "color": "yellow_background"
                            }
                        })
                
                # 创建 Toggle 块（包含所有子内容）
                blocks.append({
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": toggle_title,
                        "color": "default",
                        "children": toggle_children
                    }
                })
        
        # 底部分隔线
        blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        
        # 尾部信息（使用醒目的 callout）
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "💬"},
                "color": "pink_background",
                "rich_text": [{
                    "type": "text",
                    "text": {"content": "💡 有任何意见或建议？请在下方评论区留言，我们会认真阅读每一条反馈！感谢您的支持！❤️"}
                }]
            }
        })
        
        return blocks
    
    async def upload_to_notion(self, page_id, blocks, notion_token):
        """
        上传 blocks 到 Notion 页面
        
        Args:
            page_id: Notion 页面 ID
            blocks: blocks 列表
            notion_token: Notion Integration Token
            
        Returns:
            dict: 上传结果 {success: bool, message: str, blocks_added: int}
        """
        try:
            from notion_client import AsyncClient
            from notion_client import APIResponseError, APIErrorCode
            
            # 初始化 Notion 客户端
            notion = AsyncClient(auth=notion_token)
            
            # 1. 先清空页面现有内容
            log.info(f"[Notion上传] 获取页面现有 blocks...")
            try:
                existing_blocks = await notion.blocks.children.list(block_id=page_id)
                block_ids_to_delete = [block['id'] for block in existing_blocks.get('results', [])]
                
                if block_ids_to_delete:
                    log.info(f"[Notion上传] 删除 {len(block_ids_to_delete)} 个旧 blocks...")
                    for block_id in block_ids_to_delete:
                        await notion.blocks.delete(block_id=block_id)
                    log.info(f"[Notion上传] 已清空页面内容")
            except Exception as e:
                log.warning(f"[Notion上传] 清空页面内容失败（可能页面为空）: {e}")
            
            # 2. 分批上传新 blocks（Notion API 限制每次最多 100 个）
            batch_size = 100
            total_added = 0
            
            for i in range(0, len(blocks), batch_size):
                batch = blocks[i:i+batch_size]
                
                # 清理 blocks（移除 "object" 字段）
                cleaned_batch = self._clean_blocks_for_upload(batch)
                
                log.info(f"[Notion上传] 上传批次 {i//batch_size + 1}: {len(cleaned_batch)} blocks")
                
                try:
                    response = await notion.blocks.children.append(
                        block_id=page_id,
                        children=cleaned_batch
                    )
                    total_added += len(cleaned_batch)
                    log.info(f"[Notion上传] 批次上传成功，累计 {total_added}/{len(blocks)} blocks")
                    
                except APIResponseError as error:
                    if error.code == APIErrorCode.ValidationError:
                        error_msg = f"Notion API 验证错误: {error.body}"
                        log.error(f"[Notion上传失败] {error_msg}")
                        return {
                            'success': False,
                            'message': error_msg,
                            'blocks_added': total_added
                        }
                    else:
                        raise
            
            # 3. 更新页面信息
            self.set_page_info(page_id)
            
            log.info(f"✅ [Notion上传成功] 共上传 {total_added} 个 blocks")
            return {
                'success': True,
                'message': f'成功上传 {total_added} 个 blocks',
                'blocks_added': total_added
            }
            
        except ImportError:
            error_msg = "未安装 notion-client，请运行: pip install notion-client"
            log.error(f"[Notion上传失败] {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'blocks_added': 0
            }
        except Exception as e:
            import traceback
            error_msg = f"上传失败: {str(e)}"
            log.error(f"[Notion上传失败] {error_msg}\n{traceback.format_exc()}")
            return {
                'success': False,
                'message': error_msg,
                'blocks_added': 0
            }
    
    def _clean_blocks_for_upload(self, blocks):
        """
        清理 blocks 以符合 Notion API 格式（递归移除 "object" 字段）
        
        Args:
            blocks: blocks 列表
            
        Returns:
            list: 清理后的 blocks
        """
        def clean_block(block):
            if isinstance(block, dict):
                cleaned = {}
                for k, v in block.items():
                    if k == 'object':
                        continue
                    elif k == 'children' and isinstance(v, list):
                        cleaned[k] = [clean_block(child) for child in v]
                    elif isinstance(v, dict):
                        cleaned[k] = clean_block(v)
                    elif isinstance(v, list):
                        cleaned[k] = [clean_block(item) if isinstance(item, dict) else item for item in v]
                    else:
                        cleaned[k] = v
                return cleaned
            return block
        
        return [clean_block(block) for block in blocks]
    
    def set_page_info(self, page_id, public_url=None):
        """
        设置页面信息
        
        Args:
            page_id: Notion 页面 ID
            public_url: 公开访问 URL
        """
        self.page_id = page_id
        self.public_url = public_url
        import datetime
        self.last_sync = datetime.datetime.now()
        log.info(f"Notion 帮助文档页面已设置: {page_id}")
    
    def get_public_url(self):
        """
        获取公开访问 URL
        
        Returns:
            str: 公开 URL 或 None
        """
        return self.public_url
    
    def clear_cache(self):
        """清除缓存"""
        self.page_id = None
        self.public_url = None
        self.last_sync = None


# 全局实例
notion_help_manager = NotionHelpManager()
