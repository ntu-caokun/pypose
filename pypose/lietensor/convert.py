import warnings
import torch

from pypose.lietensor.lietensor import LieTensor, SE3_type, SO3_type, Sim3_type, RxSO3_type
from .utils import SO3, SE3, RxSO3, Sim3


def mat2SO3(mat, check=False):
    r"""Convert batched rotation or transformation matrices to SO3Type LieTensor.

    Args:
        mat (Tensor): the matrix to convert.
        check (bool, optional): flag to check if the input is valid rotation matrices (orthogonal
            and with a determinant of one). More computation is needed if ``True``.
            Default: ``False``.

    Return:
        LieTensor: the converted SO3Type LieTensor.

    Shape:
        Input: :obj:`(*, 3, 3)` or :obj:`(*, 3, 4)` or :obj:`(*, 4, 4)`

        Output: :obj:`(*, 4)`

    .. math::
        \mathbf{q}_i = 
        \left\{\begin{aligned}
        &\mathrm{sign}(R^{2,3}_i - R^{3,2}_i) \frac{1}{2} \sqrt{1 + R^{1,1}_i - R^{2,2}_i - R^{3,3}_i}\\
        &\mathrm{sign}(R^{3,1}_i - R^{1,3}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i + R^{2,2}_i - R^{3,3}_i}\\
        &\mathrm{sign}(R^{1,2}_i - R^{2,1}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i - R^{2,2}_i + R^{3,3}_i}\\
        &\frac{1}{2} \sqrt{1 + R^{1,1}_i + R^{2,2}_i + R^{3,3}_i}
        \end{aligned}\right.,
    
    where :math:`R_i` and :math:`\mathbf{q_i} = [q^x_i, q^y_i, q^z_i, q^w_i]` are the input matrices
    and output LieTensor, respectively.

    Warning:
        A rotation matrix is consided illegal if, :math:`\vert R\vert\neq1` or 
        :math:`RR^{T}\neq \mathrm{I}`. If ``check`` was set to ``True``, illegal input will raise 
        a ``ValueError``, since the function will ouput irrelevant result, likely contains ``nan``.

    Examples:

        >>> input = torch.tensor([[0., -1.,  0.],
        ...                       [1.,  0.,  0.],
        ...                       [0.,  0.,  1.]])
        >>> pp.mat2SO3(input)
        SO3Type LieTensor:
        tensor([0.0000, 0.0000, 0.7071, 0.7071])

    See :meth:`pypose.SO3` for more details of the output LieTensor format.
    """

    if not torch.is_tensor(mat):
        mat = torch.tensor(mat)

    if len(mat.shape) < 2:
        raise ValueError("Input size must be at least 2 dimensions. Got {}".format(mat.shape))

    if not (mat.shape[-2:] == (3, 3) or mat.shape[-2:] == (3, 4) or mat.shape[-2:] == (4, 4)):
        raise ValueError("Input size must be a * x 3 x 3 or * x 3 x 4 or * x 4 x 4 tensor. \
                Got {}".format(mat.shape))

    mat = mat[..., :3, :3]
    shape = mat.shape

    if check:
        e0 = mat @ mat.mT
        e1 = torch.eye(3, dtype=mat.dtype).repeat(shape[:-2] + (1, 1))
        if not torch.allclose(e0, e1, atol=torch.finfo(e0.dtype).resolution):
            raise ValueError("Input rotation matrices are not all orthogonal matrix")

        if not torch.allclose(torch.det(mat), torch.ones(shape[:-2], dtype=mat.dtype), \
                atol=torch.finfo(e0.dtype).resolution):
            raise ValueError("Input rotation matrices' determinant are not all equal to 1")

    rmat_t = mat.mT

    mask_d2 = rmat_t[..., 2, 2] < torch.finfo(mat.dtype).resolution

    mask_d0_d1 = rmat_t[..., 0, 0] > rmat_t[..., 1, 1]
    mask_d0_nd1 = rmat_t[..., 0, 0] < -rmat_t[..., 1, 1]

    t0 = 1 + rmat_t[..., 0, 0] - rmat_t[..., 1, 1] - rmat_t[..., 2, 2]
    q0 = torch.stack([rmat_t[..., 1, 2] - rmat_t[..., 2, 1],
                      t0, rmat_t[..., 0, 1] + rmat_t[..., 1, 0],
                      rmat_t[..., 2, 0] + rmat_t[..., 0, 2]], -1)
    t0_rep = t0.unsqueeze(-1).repeat((len(list(shape))-2)*(1,)+(4,))

    t1 = 1 - rmat_t[..., 0, 0] + rmat_t[..., 1, 1] - rmat_t[..., 2, 2]
    q1 = torch.stack([rmat_t[..., 2, 0] - rmat_t[..., 0, 2],
                      rmat_t[..., 0, 1] + rmat_t[..., 1, 0],
                      t1, rmat_t[..., 1, 2] + rmat_t[..., 2, 1]], -1)
    t1_rep = t1.unsqueeze(-1).repeat((len(list(shape))-2)*(1,)+(4,))

    t2 = 1 - rmat_t[..., 0, 0] - rmat_t[..., 1, 1] + rmat_t[..., 2, 2]
    q2 = torch.stack([rmat_t[..., 0, 1] - rmat_t[..., 1, 0],
                      rmat_t[..., 2, 0] + rmat_t[..., 0, 2],
                      rmat_t[..., 1, 2] + rmat_t[..., 2, 1], t2], -1)
    t2_rep = t2.unsqueeze(-1).repeat((len(list(shape))-2)*(1,)+(4,))

    t3 = 1 + rmat_t[..., 0, 0] + rmat_t[..., 1, 1] + rmat_t[..., 2, 2]
    q3 = torch.stack([t3, rmat_t[..., 1, 2] - rmat_t[..., 2, 1],
                      rmat_t[..., 2, 0] - rmat_t[..., 0, 2],
                      rmat_t[..., 0, 1] - rmat_t[..., 1, 0]], -1)
    t3_rep = t3.unsqueeze(-1).repeat((len(list(shape))-2)*(1,)+(4,))

    mask_c0 = mask_d2 * mask_d0_d1
    mask_c1 = mask_d2 * ~mask_d0_d1
    mask_c2 = ~mask_d2 * mask_d0_nd1
    mask_c3 = ~mask_d2 * ~mask_d0_nd1
    mask_c0 = mask_c0.unsqueeze(-1).type_as(q0)
    mask_c1 = mask_c1.unsqueeze(-1).type_as(q1)
    mask_c2 = mask_c2.unsqueeze(-1).type_as(q2)
    mask_c3 = mask_c3.unsqueeze(-1).type_as(q3)

    q = q0 * mask_c0 + q1 * mask_c1 + q2 * mask_c2 + q3 * mask_c3
    q /= 2*torch.sqrt(t0_rep * mask_c0 + t1_rep * mask_c1 +  # noqa
                    t2_rep * mask_c2 + t3_rep * mask_c3)  # noqa

    q = q.view(shape[:-2]+(4,))
    # wxyz -> xyzw
    q = q.index_select(-1, torch.tensor([1, 2, 3, 0], device=q.device))

    return SO3(q)


def mat2SE3(mat, check=False):
    r"""Convert batched rotation or transformation matrices to SO3Type LieTensor.

    Args:
        mat (Tensor): the matrix to convert. If input is of shape :obj:`(*, 3, 3)`, then translation
            will be filled with zero.
        check (bool, optional): flag to check if the input is valid rotation matrices (orthogonal
            and with a determinant of one). More computation is needed if ``True``.
            Default: ``False``.

    Return:
        LieTensor: the converted SE3Type LieTensor.

    Shape:
        Input: :obj:`(*, 3, 3)` or :obj:`(*, 3, 4)` or :obj:`(*, 4, 4)`

        Output: :obj:`(*, 7)`

    Suppose the input transformation matrix :math:`T_i\in\mathbb{R}^{4\times 4}`,
    let :math:`R_i\in\mathbb{R}^{3\times 3}` be the upper left 3 by 3 submatrix of :math:`T_i`.  
    Let :math:`T^{m,n}_i` be the element of row :math:`m` and coloum :math:`n` in :math:`T_i`, 
    then the translation and quaternion can be computed by:
    
    .. math::
        \left\{\begin{aligned}
        t^x_i &= T^{1,4}_i\\
        t^y_i &= T^{2,4}_i\\
        t^z_i &= T^{3,4}_i\\
        q^x_i &= \mathrm{sign}(R^{2,3}_i - R^{3,2}_i) \frac{1}{2} \sqrt{1 + R^{1,1}_i - R^{2,2}_i - R^{3,3}_i}\\
        q^y_i &= \mathrm{sign}(R^{3,1}_i - R^{1,3}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i + R^{2,2}_i - R^{3,3}_i}\\
        q^z_i &= \mathrm{sign}(R^{1,2}_i - R^{2,1}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i - R^{2,2}_i + R^{3,3}_i}\\
        q^w_i &= \frac{1}{2} \sqrt{1 + R^{1,1}_i + R^{2,2}_i + R^{3,3}_i}
        \end{aligned}\right.,

    In summary, the output LieTensor should be of format:

    .. math::
        \textbf{y}_i = [t^x_i, t^y_i, t^z_i, q^x_i, q^y_i, q^z_i, q^w_i]

    Warning:
        A rotation matrix is consided illegal if, :math:`\vert R\vert\neq1` or 
        :math:`RR^{T}\neq \mathrm{I}`. If ``check`` was set to ``True``, illegal input will
        raise a ``ValueError``, since the function will ouput irrelevant result, likely contains ``nan``.

    Examples:

        >>> input = torch.tensor([[0., -1., 0., 0.1],
        ...                       [1.,  0., 0., 0.2],
        ...                       [0.,  0., 1., 0.3],
        ...                       [0.,  0., 0.,  1.]])
        >>> pp.mat2SE3(input)
        SE3Type LieTensor:
        tensor([0.1000, 0.2000, 0.3000, 0.0000, 0.0000, 0.7071, 0.7071])

    Note:
        Input matrices can be written as:

        .. math::
            \begin{bmatrix}
                    R_{3\times3} & \mathbf{t}_{3\times1}\\
                    \textbf{0} & 1
            \end{bmatrix},

        where :math:`R` is the rotation matrix. The translation vector :math:`\mathbf{t}` defines the
        displacement between the original position and the transformed position.


    See :meth:`pypose.SE3` for more details of the output LieTensor format.
    """
    if not torch.is_tensor(mat):
        mat = torch.tensor(mat)

    if len(mat.shape) < 2:
        raise ValueError("Input size must be at least 2 dimensions. Got {}".format(mat.shape))

    if not (mat.shape[-2:] == (3, 3) or mat.shape[-2:] == (3, 4) or mat.shape[-2:] == (4, 4)):
        raise ValueError("Input size must be a * x 3 x 3 or * x 3 x 4 or * x 4 x 4  tensor. \
                Got {}".format(mat.shape))

    q = mat2SO3(mat[..., :3, :3], check).tensor()
    if mat.shape[-1] == 3:
        t = torch.zeros(mat.shape[:-2]+(3,), dtype = mat.dtype, requires_grad=mat.requires_grad)
    else:
        t = mat[..., :3, 3]
    vec = torch.cat([t, q], dim=-1)

    return SE3(vec)


def mat2Sim3(mat, check=False):
    r"""Convert batched rotation or transformation matrices to Sim3Type LieTensor.

    Args:
        mat (Tensor): the matrix to convert. If input is of shape :obj:`(*, 3, 3)`, 
            then translation will be filled with zero.
        check (bool, optional): flag to check if the input is valid rotation matrices (orthogonal
            and with a determinant of one). More computation is needed if ``True``.
            Default: ``False``.

    Return:
        LieTensor: the converted Sim3Type LieTensor.

    Shape:
        Input: :obj:`(*, 3, 3)` or :obj:`(*, 3, 4)` or :obj:`(*, 4, 4)`

        Output: :obj:`(*, 8)`

    Suppose the input transformation matrix :math:`T_i\in\mathbb{R}^{4\times 4}`,
    let :math:`U_i\in\mathbb{R}^{3\times 3}` be the upper left 3 by 3 submatrix of :math:`T_i`,
    then the scaling factor :math:`s_i\in\mathbb{R}` and the rotation matrix
    :math:`R_i\in\mathbb{R}^{3\times 3}` can be computed as:

    .. math::
        \begin{aligned}
            s_i &= \sqrt[3]{\vert U_i \vert}\\
            R_i &= U_i/s_i
        \end{aligned}
    
    Let :math:`T^{m,n}_i` be the element of row :math:`m` and coloum :math:`n` in :math:`T_i`, 
    then the translation and quaternion can be computed by:

    .. math::
        \left\{\begin{aligned}
        t^x_i &= T^{1,4}_i\\
        t^y_i &= T^{2,4}_i\\
        t^z_i &= T^{3,4}_i\\
        q^x_i &= \mathrm{sign}(R^{2,3}_i - R^{3,2}_i) \frac{1}{2} \sqrt{1 + R^{1,1}_i - R^{2,2}_i - R^{3,3}_i}\\
        q^y_i &= \mathrm{sign}(R^{3,1}_i - R^{1,3}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i + R^{2,2}_i - R^{3,3}_i}\\
        q^z_i &= \mathrm{sign}(R^{1,2}_i - R^{2,1}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i - R^{2,2}_i + R^{3,3}_i}\\
        q^w_i &= \frac{1}{2} \sqrt{1 + R^{1,1}_i + R^{2,2}_i + R^{3,3}_i}
        \end{aligned}\right.,
    
    In summary, the output LieTensor should be of format:

    .. math::
        \textbf{y}_i = [t^x_i, t^y_i, t^z_i, q^x_i, q^y_i, q^z_i, q^w_i, s_i]

    Warning:
        If :math:`s_i` contains zero value, then the function will raise a ``ValueError``, since
        further computation leads to *nan* in the computed quaternions.

        A rotation matrix is consided illegal if, :math:`\vert R\vert\neq1` or 
        :math:`RR^{T}\neq \mathrm{I}`. If ``check`` was set to ``True``, illegal input will raise 
        a ``ValueError``, since the function will ouput irrelevant result, likely contains ``nan``.
        
    Examples:
        >>> input = torch.tensor([[ 0.,-0.5,  0., 0.1],
        ...                       [0.5,  0.,  0., 0.2],
        ...                       [ 0.,  0., 0.5, 0.3],
        ...                       [ 0.,  0.,  0.,  1.]])
        >>> pp.mat2Sim3(input)
        Sim3Type LieTensor:
        tensor([0.1000, 0.2000, 0.3000, 0.0000, 0.0000, 0.7071, 0.7071, 0.5000])

    Note:
        Input matrices can be written as:
        
        .. math::
            \begin{bmatrix}
                    sR_{3\times3} & \mathbf{t}_{3\times1}\\
                    \textbf{0} & 1
            \end{bmatrix},

        where :math:`R` is the rotation matrix. The scaling factor :math:`s` defines a linear
        transformation that enlarges or diminishes the object in the same ratio across 3 dimensions,
        the translation vector :math:`\mathbf{t}` defines the displacement between the original position and
        the transformed position.

    See :meth:`pypose.Sim3` for more details of the output LieTensor format.
    """
    if not torch.is_tensor(mat):
        mat = torch.tensor(mat)

    if len(mat.shape) < 2:
        raise ValueError("Input size must be at least 2 dimensions. Got {}".format(mat.shape))

    if not (mat.shape[-2:] == (3, 3) or mat.shape[-2:] == (3, 4) or mat.shape[-2:] == (4, 4)):
        raise ValueError("Input size must be a * x 3 x 3 or * x 3 x 4 or * x 4 x 4  tensor. \
                Got {}".format(mat.shape))

    shape = mat.shape
    rot = mat[..., :3, :3]

    s = torch.pow(torch.det(mat), 1/3).unsqueeze(-1)
    if torch.any(torch.isclose(s,  torch.zeros(shape[:-2], dtype=mat.dtype), \
                atol=torch.finfo(mat.dtype).resolution)):
        raise ValueError("Rotation matrix not full rank.")

    q = mat2SO3(rot/s.unsqueeze(-1), check).tensor()

    if mat.shape[-1] == 3:
        t = torch.zeros(mat.shape[:-2]+(3,), dtype=mat.dtype, requires_grad=mat.requires_grad)
    else:
        t = mat[..., :3, 3]

    vec = torch.cat([t, q, s], dim=-1)

    return Sim3(vec)


def mat2RxSO3(mat, check=False):
    r"""Convert batched rotation or transformation matrices to RxSO3Type LieTensor.

    Args:
        mat (Tensor): the matrix to convert.
        check (bool, optional): flag to check if the input is valid rotation matrices (orthogonal
            and with a determinant of one). More computation is needed if ``True``.
            Default: ``False``.

    Return:
        LieTensor: the converted RxSO3Type LieTensor.

    Shape:
        Input: :obj:`(*, 3, 3)` or :obj:`(*, 3, 4)` or :obj:`(*, 4, 4)`

        Output: :obj:`(*, 5)`
    
    Suppose the input transformation matrix :math:`T_i\in\mathbb{R}^{3\times 3}`, 
    then the scaling factor :math:`s_i\in\mathbb{R}` and the rotation matrix
    :math:`R_i\in\mathbb{R}^{3\times 3}` can be computed as:

    .. math::
        \begin{aligned}
            s_i &= \sqrt[3]{\vert T_i \vert}\\
            R_i &= R_i/s_i
        \end{aligned}
    
    Let :math:`R^{m,n}_i` be the element of row :math:`m` and coloum :math:`n` in :math:`R_i`, then
    the quaternion can be computed by:
    
    .. math::
        \left\{\begin{aligned}
        q^x_i &= \mathrm{sign}(R^{2,3}_i - R^{3,2}_i) \frac{1}{2} \sqrt{1 + R^{1,1}_i - R^{2,2}_i - R^{3,3}_i}\\
        q^y_i &= \mathrm{sign}(R^{3,1}_i - R^{1,3}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i + R^{2,2}_i - R^{3,3}_i}\\
        q^z_i &= \mathrm{sign}(R^{1,2}_i - R^{2,1}_i) \frac{1}{2} \sqrt{1 - R^{1,1}_i - R^{2,2}_i + R^{3,3}_i}\\
        q^w_i &= \frac{1}{2} \sqrt{1 + R^{1,1}_i + R^{2,2}_i + R^{3,3}_i}
        \end{aligned}\right.,
    
    In summary, the output LieTensor should be of format:

    .. math::
        \textbf{y}_i = [q^x_i, q^y_i, q^z_i, q^w_i, s_i]

    Warning:
        If :math:`s_i` contains zero value, then the function will raise a ``ValueError``, since
        further computation leads to *nan* in the computed quaternions.

        A rotation matrix is consided illegal if, :math:`\vert R\vert\neq1` or 
        :math:`RR^{T}\neq \mathrm{I}`. If ``check`` was set to ``True``, illegal input will raise 
        a ``ValueError``, since the function will ouput irrelevant result, likely contains ``nan``.

    Examples:
        >>> input = torch.tensor([[ 0., -0.5,  0.],
        ...                       [0.5,   0.,  0.],
        ...                       [ 0.,   0., 0.5]])
        >>> pp.mat2RxSO3(input)
        RxSO3Type LieTensor:
        tensor([0.0000, 0.0000, 0.7071, 0.7071, 0.5000])

    Note:
        Input matrices can be written as :math:`sR_{3\times3}`, where :math:`R` is the rotation
        matrix. where  the scaling factor :math:`s` defines a linear transformation that enlarges
        or diminishes the object in the same ratio across 3 dimensions.

    See :meth:`pypose.RxSO3` for more details of the output LieTensor format.
    """
    if not torch.is_tensor(mat):
        mat = torch.tensor(mat)

    if len(mat.shape) < 2:
        raise ValueError("Input size must be at least 2 dimensions. Got {}".format(mat.shape))

    if not (mat.shape[-2:] == (3, 3) or mat.shape[-2:] == (3, 4) or mat.shape[-2:] == (4, 4)):
        raise ValueError("Input size must be a * x 3 x 3 or * x 3 x 4 or * x 4 x 4  tensor. \
                Got {}".format(mat.shape))

    shape = mat.shape
    rot = mat[..., :3, :3]

    s = torch.pow(torch.det(mat), 1/3).unsqueeze(-1)
    if torch.any(torch.isclose(s,  torch.zeros(shape[:-2], dtype=mat.dtype), \
                atol=torch.finfo(mat.dtype).resolution)):
        raise ValueError("Rotation matrix not full rank.")

    q = mat2SO3(rot/s.unsqueeze(-1), check).tensor()
    vec = torch.cat([q, s], dim=-1)

    return RxSO3(vec)


def from_matrix(mat, ltype, check=False):
    r"""Convert batched rotation or transformation matrices to LieTensor.

    Args:
        mat (Tensor): the matrix to convert.
        ltype (ltype): specify the LieTensor type, chosen from :class:`pypose.SO3_type`,
            :class:`pypose.SE3_type`, :class:`pypose.Sim3_type`, or :class:`pypose.RxSO3_type`.
            See more details in :meth:`LieTensor`
        check (bool, optional): flag to check if the input is valid rotation matrices (orthogonal
            and with a determinant of one). More computation is needed if ``True``. Default: ``False``.

    Warning:
        A rotation matrix is consided illegal if, :math:`\vert R\vert\neq1` or 
        :math:`RR^{T}\neq \mathrm{I}`. If ``check`` was set to ``True``, illegal input
        will raise a ``ValueError``, since the function will ouput irrelevant result, likely contains ``nan``.
    
    Return:
        LieTensor: the converted LieTensor.
    Examples:

        - :class:`pypose.SO3_type`

        >>> pp.from_matrix(torch.tensor([[0., -1., 0.],
        ...                              [1.,  0., 0.],
        ...                              [0.,  0., 1.]]), ltype=pp.SO3_type)
        SO3Type LieTensor:
        tensor([0.0000, 0.0000, 0.7071, 0.7071])

        - :class:`pypose.SE3_type`

        >>> pp.from_matrix(torch.tensor([[0., -1., 0., 0.1],
        ...                              [1.,  0., 0., 0.2],
        ...                              [0.,  0., 1., 0.3],
        ...                              [0.,  0., 0.,  1.]]), ltype=pp.SE3_type)
        SE3Type LieTensor:
        tensor([0.1000, 0.2000, 0.3000, 0.0000, 0.0000, 0.7071, 0.7071])

        - :class:`pypose.Sim3_type`

        >>> pp.from_matrix(torch.tensor([[ 0.,-0.5,  0., 0.1],
        ...                              [0.5,  0.,  0., 0.2],
        ...                              [ 0.,  0., 0.5, 0.3],
        ...                              [ 0.,  0.,  0.,  1.]]), ltype=pp.Sim3_type)
        Sim3Type LieTensor:
        tensor([0.1000, 0.2000, 0.3000, 0.0000, 0.0000, 0.7071, 0.7071, 0.5000])

        - :class:`pypose.RxSO3_type`

        >>> pp.from_matrix(torch.tensor([[0., -0.5, 0.],
        ...                              [0.5, 0.,  0.],
        ...                              [0.,  0., 0.5]]), ltype=pp.RxSO3_type)
        RxSO3Type LieTensor:
        tensor([0.0000, 0.0000, 0.7071, 0.7071, 0.5000])
    """
    if not torch.is_tensor(mat):
        mat = torch.tensor(mat)

    if len(mat.shape) < 2:
        raise ValueError("Input size must be at least 2 dimensions. Got {}".format(mat.shape))

    if not (mat.shape[-2:] == (3, 3) or mat.shape[-2:] == (3, 4) or mat.shape[-2:] == (4, 4)):
        raise ValueError("Input size must be a * x 3 x 3 or * x 3 x 4 or * x 4 x 4  tensor. \
                Got {}".format(mat.shape))

    if ltype == SO3_type:
        return mat2SO3(mat, check)
    elif ltype == SE3_type:
        return mat2SE3(mat, check)
    elif ltype == Sim3_type:
        return mat2Sim3(mat, check)
    elif ltype == RxSO3_type:
        return mat2RxSO3(mat, check)
    else:
        raise ValueError("Input ltype must be one of SO3_type, SE3_type, Sim3_type or RxSO3_type.\
                Got {}".format(ltype))


def matrix(lietensor):
    assert isinstance(lietensor, LieTensor)
    return lietensor.matrix()


def euler2SO3(euler: torch.Tensor):
    r"""Convert batched Euler angles (roll, pitch, and yaw) to SO3Type LieTensor.

    Args:
        euler (Tensor): the euler angles to convert.

    Return:
        LieTensor: the converted SO3Type LieTensor.

    Shape:
        Input: :obj:`(*, 3)`

        Output: :obj:`(*, 4)`

    .. math::
        {\displaystyle \mathbf{y}_i={
        \begin{bmatrix}\,
        \sin(\alpha_i)\cos(\beta_i)\cos(\gamma_i) - \cos(\alpha_i)\sin(\beta_i)\sin(\gamma_i)\\\,
        \cos(\alpha_i)\sin(\beta_i)\cos(\gamma_i) + \sin(\alpha_i)\cos(\beta_i)\sin(\gamma_i)\\\,
        \cos(\alpha_i)\cos(\beta_i)\sin(\gamma_i) - \sin(\alpha_i)\sin(\beta_i)\cos(\gamma_i)\\\,
        \cos(\alpha_i)\cos(\beta_i)\cos(\gamma_i) + \sin(\alpha_i)\sin(\beta_i)\sin(\gamma_i)
        \end{bmatrix}}},

    where the :math:`i`-th item of input :math:`\mathbf{x}_i = [\alpha_i, \beta_i, \gamma_i]`
    are roll, pitch, and yaw, respectively.

    Note:
        The last dimension of the input tensor has to be 3.

    Examples:
        >>> input = torch.randn(2, 3, requires_grad=True, dtype=torch.float64)
        >>> pp.euler2SO3(input)
        SO3Type LieTensor:
        tensor([[-0.4873,  0.1162,  0.4829,  0.7182],
                [ 0.3813,  0.4059, -0.2966,  0.7758]], dtype=torch.float64, grad_fn=<AliasBackward0>)
    """
    if not torch.is_tensor(euler):
        euler = torch.tensor(euler)
    assert euler.shape[-1] == 3
    shape, euler = euler.shape, euler.view(-1, 3)
    roll, pitch, yaw = euler[:, 0], euler[:, 1], euler[:, 2]
    cy, sy = (yaw * 0.5).cos(), (yaw * 0.5).sin()
    cp, sp = (pitch * 0.5).cos(), (pitch * 0.5).sin()
    cr, sr = (roll * 0.5).cos(), (roll * 0.5).sin()

    q = torch.stack([sr * cp * cy - cr * sp * sy,
                     cr * sp * cy + sr * cp * sy,
                     cr * cp * sy - sr * sp * cy,
                     cr * cp * cy + sr * sp * sy], dim=-1)
    return SO3(q).lview(*shape[:-1])
