from typing import Tuple

from webdnn.graph import traverse
from webdnn.graph.axis import Axis
from webdnn.graph.graph import Graph
from webdnn.graph.operators.convolution2d import Convolution2D
from webdnn.graph.operators.im2col import Im2Col
from webdnn.graph.operators.sgemm import Sgemm
from webdnn.graph.optimize_rule import OptimizeRule
from webdnn.graph.order import OrderNHWC, OrderHWCN
from webdnn.graph.variables.constant_variable import ConstantVariable


class ReplaceConvolutionByIm2Col(OptimizeRule):
    """
    Replace Convolution2D by Im2Col and SGEMM
    """

    def optimize(self, graph: Graph) -> Tuple[Graph, bool]:
        flag_changed = False
        for op in traverse.filter_nodes(traverse.listup_operators(graph), Convolution2D):  # type: Convolution2D
            x = op.inputs["x"]
            w = op.inputs["w"]
            y = op.outputs["y"]

            assert x.order == OrderNHWC
            assert y.order == OrderNHWC
            assert isinstance(w, ConstantVariable)

            flag_changed = True
            op.remove_all()
            w.change_order(OrderHWCN)

            if op.WH != 1 or op.WW != 1 or op.stride != (1, 1) or op.padding != (0, 0):
                im2col = Im2Col(None, ksize=op.ksize, stride=op.stride, padding=op.padding,
                                dilation_rate=op.dilation_rate)
                col, = im2col(x)
                col.change_order(OrderNHWC)

            else:
                col = x

            sgemm = Sgemm(None,
                          M=col.shape_dict[Axis.N] * col.shape_dict[Axis.H] * col.shape_dict[Axis.W],
                          N=w.shape_dict[Axis.N],
                          K=col.shape_dict[Axis.C],
                          out_shape=[col.shape_dict[Axis.N], col.shape_dict[Axis.H], col.shape_dict[Axis.W], w.shape_dict[Axis.N]],
                          out_order=OrderNHWC,
                          transpose_A=True if col.order == OrderNHWC else False,
                          transpose_B=True)

            new_y, = sgemm(col, w)
            new_y.replace(y)

        return graph, flag_changed