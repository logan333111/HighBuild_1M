#!/bin/bash
# 激活你的 conda 环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate bh_env

echo "========================================="
echo "  🚀 城市网格法高清数据集生成器"
echo "========================================="

# 运行主数据集提取脚本
# 修改 --input 参数来切换不同的 geojson 文件:
#   hznu.geojson       (31 栋, 快速测试)
#   graz.geojson       (15 万栋, 中等规模)
#   Copenhagen.geojson (75 万栋, 大规模)
echo -e "\n---> 开始生成数据集 <---"
python src/make_dataset.py --input hznu.geojson

echo -e "\n🎉 运行完毕！"

conda activate bh_env

python  src/download_image.py --geojson  geojson  --source 