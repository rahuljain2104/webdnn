from typing import List

from webdnn.backend.code_generator.allocator import MemoryLayout
from webdnn.backend.code_generator.injectors.buffer_injector import BufferInjector
from webdnn.backend.code_generator.injectors.kernel_name_injector import KernelNameInjector
from webdnn.backend.webgpu.kernel import GPUSize, Kernel
from webdnn.backend.webgpu.preset_placeholders import MAX_THREADS_PER_THREADGROUP
from webdnn.graph.operators.threshold_relu import ThresholdRelu

template = """
kernel void %%FUNC_NAME%%(device float * %%STATIC_BUFFER%%[[buffer(0)]],
                          device float * %%DYNAMIC_BUFFER%%[[buffer(1)]],
                          const device int * %%META_BUFFER%% [[buffer(2)]],
                          uint index[[thread_position_in_grid]],
                          uint num_threads[[threads_per_grid]])
{
    const device float *X = %%LOAD_BUFFER(threshold_relu_X)%%;
    device float *Y = %%LOAD_BUFFER(threshold_relu_Y)%%;

    const int N = %%LOAD_BUFFER(threshold_relu_N)%%;
    const float t = *((device float *)(& %%LOAD_BUFFER(threshold_relu_t)%%));
  
    for (int gid = index; gid < N; gid += num_threads) {
        float result = X[gid];
        result = result < t ? 0.0 : result;      

        Y[gid] = result;
    }
}
"""


def threshold_relu(op: ThresholdRelu,
         memory_layout: MemoryLayout) -> List[Kernel]:
    x = memory_layout[op.inputs["x0"]]
    y = memory_layout[op.outputs["y"]]

    assert x.variable.shape == y.variable.shape

    buffer_injector = BufferInjector()
    buffer_injector.register({
        "threshold_relu_X": x,
        "threshold_relu_Y": y,
        "threshold_relu_N": y.variable.size,
        "threshold_relu_t": float(op.threshold)
    })

    name_injector = KernelNameInjector(op)

    source = template
    source = buffer_injector.inject(source)
    source = name_injector.inject(source)

    kernel = Kernel(
        {name_injector.name: source},
        name_injector.name,
        GPUSize(8, 1, 1),
        GPUSize(MAX_THREADS_PER_THREADGROUP, 1, 1),
        buffer_injector.buffer,
        buffer_injector.unresolved_value_list
    )

    return [kernel]
