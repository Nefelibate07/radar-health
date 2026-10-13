// 从左到右分层布局：监控计算机在最左列，它的直接下级排在第二列，第二列子系统的
// 下级排在第三列，依次向右类推——即按到根节点的最短路径深度分列，同一列内的卡片
// 沿垂直方向均匀排开。拓扑表里没有任何连线的孤立节点（演示端、用户操作端）不
// 参与分列，固定放在最右侧单独的一小列里。
//
// 之前用监控计算机居中、下级绕着它一圈一圈摆的放射状布局，在窗口不是全屏、比较窄
// 矮的情况下，最密的一圈有 13 个节点，无论怎么调间距参数，最终都会在某些角度上把
// 卡片和箭头挤在一起——这是"一圈只有这么大周长却要塞 13 张卡片"的几何限制，不是参
// 数没调好。改成分层布局后，最密的一层（13 个节点）不再挤在同一小段弧长上，而是从
// 上到下摆一整列，可以用满容器的整个高度；如果容器矮到连一整列都放不下这么多张卡
// 片，就把这一列的卡片高度自动缩小（而不是让它们叠在一起），保证不重叠始终是硬约束，
// 紧凑程度是在这个前提下尽量做到最好。
export function buildColumnLayout(edges, rootId, options = {}) {
  const {
    extraIds = [],
    width = 900,
    height = 620,
    cardWidth = 88,
    cardHeight = 50,
    hubSize = 60,
    marginPx = 8,
    gapPx = 8,
    minCardHeight = 26
  } = options

  const children = new Map()
  edges.forEach(([from, to]) => {
    if (!children.has(from)) children.set(from, [])
    children.get(from).push(to)
  })

  // BFS 求每个节点到根节点的最短距离（同一个节点可能有多个上级，取最短路径所在的列）
  const depth = new Map([[rootId, 0]])
  const queue = [rootId]
  while (queue.length) {
    const node = queue.shift()
    const d = depth.get(node)
    for (const child of children.get(node) || []) {
      if (!depth.has(child)) {
        depth.set(child, d + 1)
        queue.push(child)
      }
    }
  }

  const columns = new Map([[0, [rootId]]])
  depth.forEach((d, id) => {
    if (d === 0) return
    if (!columns.has(d)) columns.set(d, [])
    columns.get(d).push(id)
  })
  const maxDepth = Math.max(0, ...depth.values())
  const numCols = maxDepth + 1

  const isolatedIds = extraIds.filter((id) => !depth.has(id))

  // 列的横向位置全部按像素计算再换算成百分比，而不是直接假设一个固定百分比——
  // 否则容器较窄时，卡片自身的像素宽度占比会变大，之前用固定百分比时就在最右边
  // 出界过。这里显式给最左（监控计算机的圆）和最右（孤立节点列）都留出正好够
  // 放下卡片一半宽度加安全间距的空间，中间的分层列再在这段可用像素范围内等分。
  const halfHub = hubSize / 2
  const halfCard = cardWidth / 2
  const isolatedReservePx = isolatedIds.length ? cardWidth + marginPx * 3 : 0
  const xMinPx = halfHub + marginPx
  const xMaxPx = Math.max(xMinPx, width - isolatedReservePx - halfCard - marginPx)
  const isolatedXPx = width - halfCard - marginPx

  const positions = {}
  const sizes = {}

  for (let d = 0; d <= maxDepth; d++) {
    const ids = columns.get(d) || []
    const n = ids.length
    const xPx = numCols > 1 ? xMinPx + (d / (numCols - 1)) * (xMaxPx - xMinPx) : xMinPx
    const xPct = (xPx / width) * 100
    const isHub = d === 0
    const baseW = isHub ? hubSize : cardWidth
    const baseH = isHub ? hubSize : cardHeight

    if (n <= 1) {
      const yPx = height / 2
      ids.forEach((id) => {
        positions[id] = { x: xPct, y: (yPx / height) * 100 }
        sizes[id] = { width: baseW, height: baseH }
      })
      continue
    }

    // 直接按整列的总高度求卡片高度：n 张卡片和 n-1 个间隙必须整体放进
    // 去掉上下安全边距后的空间。之前用有限次迭代估算时，最后一次收缩仍可能
    // 让 step 小于 cardHeight + gap，导致密集列的卡片发生垂直重叠，进而把文字
    // 挤到卡片下方。这个公式把“不重叠”作为硬约束，minCardHeight 只是正常情况
    // 下的建议下限；窗口极矮时允许继续缩小，由调用方按实际高度缩放字号。
    const availableStackPx = Math.max(0, height - marginPx * 2)
    const maxHeightWithoutOverlap = (availableStackPx - (n - 1) * gapPx) / n
    const ch = Math.max(1, Math.min(baseH, maxHeightWithoutOverlap))
    const step = ch + gapPx
    const topPx = marginPx + ch / 2

    ids.forEach((id, i) => {
      const yPx = topPx + i * step
      positions[id] = { x: xPct, y: (yPx / height) * 100 }
      sizes[id] = { width: baseW, height: ch }
    })
  }

  if (isolatedIds.length) {
    const xPct = (isolatedXPx / width) * 100
    const n = isolatedIds.length
    const availableStackPx = Math.max(0, height - marginPx * 2)
    const maxHeightWithoutOverlap = n > 1
      ? (availableStackPx - (n - 1) * gapPx) / n
      : availableStackPx
    const ch = Math.max(1, Math.min(cardHeight, maxHeightWithoutOverlap))
    const step = ch + gapPx
    isolatedIds.forEach((id, i) => {
      const yPx = n === 1 ? height / 2 : marginPx + ch / 2 + i * step
      positions[id] = { x: xPct, y: (yPx / height) * 100 }
      sizes[id] = { width: cardWidth, height: ch }
    })
  }

  return { positions, sizes, depth, maxDepth }
}

// 生成一条从下级卡片指向上级卡片的直线连接线（简单直接风格，不绕弯）。两端各沿
// 连线方向、按对方卡片的矩形边界裁剪掉一段距离（min(halfW/|方向x|, halfH/|方向y|)
// 就是矩形中心到该方向上边界的距离），保证线段真正停在卡片边缘而不是穿进卡片内部，
// 箭头也就能准确贴在卡片边上。同一列内两个上级的边也直接用这条直线连——比起之前
// 为了绕开同列卡片而单独维护一套折线偏移逻辑，直线更符合"简单直接"的要求，代价是
// 极少数这类边会贴着从同列其他卡片背后经过，但卡片本身不透明且层级更高，视觉上
// 线段只是被卡片盖住一段，不会穿到卡片前面。
export function buildStraightLine(childPos, parentPos, childHalfWPct, childHalfHPct, parentHalfWPct, parentHalfHPct, marginPct = 1) {
  const dx = parentPos.x - childPos.x
  const dy = parentPos.y - childPos.y
  const dist = Math.hypot(dx, dy) || 1
  const ux = dx / dist
  const uy = dy / dist

  const trimTo = (halfW, halfH) => {
    if (ux === 0) return halfH
    if (uy === 0) return halfW
    return Math.min(halfW / Math.abs(ux), halfH / Math.abs(uy))
  }

  const trimChild = trimTo(childHalfWPct, childHalfHPct) + marginPct
  const trimParent = trimTo(parentHalfWPct, parentHalfHPct) + marginPct
  const x1 = childPos.x + ux * trimChild
  const y1 = childPos.y + uy * trimChild
  const x2 = parentPos.x - ux * trimParent
  const y2 = parentPos.y - uy * trimParent
  return `M ${x1},${y1} L ${x2},${y2}`
}

// 生成关系图连线：跨层关系使用直线，同一层的上下级关系绕到卡片外侧，
// 避免直线穿过同列卡片后无法判断箭头究竟指向哪个上级。
export function buildRelationshipPath(
  childPos,
  parentPos,
  childHalfWPct,
  childHalfHPct,
  parentHalfWPct,
  parentHalfHPct,
  options = {}
) {
  const {
    sameColumn = false,
    routeSide = 1,
    routeOffsetPct = Math.max(childHalfWPct, parentHalfWPct) + 3
  } = options

  if (!sameColumn || Math.abs(childPos.x - parentPos.x) > 0.01) {
    return buildStraightLine(
      childPos,
      parentPos,
      childHalfWPct,
      childHalfHPct,
      parentHalfWPct,
      parentHalfHPct
    )
  }

  const side = routeSide >= 0 ? 1 : -1
  const startX = childPos.x + side * (childHalfWPct + 1)
  const endX = parentPos.x + side * (parentHalfWPct + 1)
  const routeX = Math.max(Math.abs(startX - childPos.x), Math.abs(endX - parentPos.x), routeOffsetPct)
    * side
    + childPos.x

  return `M ${startX},${childPos.y} C ${routeX},${childPos.y} ${routeX},${parentPos.y} ${endX},${parentPos.y}`
}
