# EKS durable storage prerequisites — review draft

**Status: prepared for review only. Nothing in this directory has been applied.**
One explicit approval is required for the complete IAM, add-on, StorageClass,
and bounded smoke-test plan below.

## Target and read-only discovery

Prepared 2026-11-07 for account `120736097561`, region `eu-central-1`, cluster
`nonprod-euc1` (EKS `1.36`). AWS CLI calls use the explicit local profile
`120736097561_betterix-AdministratorAccess`. No AWS access keys, session tokens,
or credential files are included in this change. Read-only checks confirmed:

- The cluster is `ACTIVE`, version `1.36`, ARN
  `arn:aws:eks:eu-central-1:120736097561:cluster/nonprod-euc1`.
- EKS Auto Mode compute is disabled, so the standard EBS CSI provisioner
  `ebs.csi.aws.com` is the applicable driver path.
- The active `nonprod-euc1` kubeconfig context endpoint exactly matches the
  endpoint returned by EKS for this cluster.
- The Pod Identity agent is ready on all 5 of 5 current nodes. The EBS CSI
  add-on is not installed;
  the current add-on list is `coredns`, `eks-pod-identity-agent`, and `kube-proxy`.
- AWS currently marks `v1.67.2-eksbuild.1` as the default EBS CSI add-on for
  Kubernetes `1.36`; it supports `amd64` and `arm64` and requires IAM permissions.
- The `splatform-gp3` StorageClass does not exist.
- The `splatform` namespace exists; the smoke-test PVC and writer/reader Pod names there do not exist.
- No `ebs.csi.aws.com` CSIDriver or self-managed EBS CSI controller/node workload
  is currently installed.
- The proposed dedicated role `nonprod-euc1-ebs-csi-controller` does not exist.
- No Pod Identity association exists for
  `kube-system/ebs-csi-controller-sa` in this cluster.
- `ec2:GetEbsDefaultKmsKeyId` returns `alias/aws/ebs` in `eu-central-1`, and
  `kms:DescribeKey` resolves it to an enabled AWS-managed regional key.
- EKS add-on configuration recommends `AmazonEBSCSIDriverPolicyV2` for this
  add-on version. This draft selects the official, more narrowly
  cluster-scoped alternative `AmazonEBSCSIDriverEKSClusterScopedPolicy` after
  confirming the current default version is v2 and every current cluster node
  has one of the cluster tags its attach/detach statements accept. See the
  policy note below before the single approval gate.
- The EFS CSI driver is present and there are no EFS filesystems; both remain
  outside this change and will not be modified.

Recheck these facts immediately before approval. Do not proceed if the cluster,
version, add-on state, role name, profile account, or policy version has changed.

## Files in this draft

- [`pod-identity-trust.json`](pod-identity-trust.json) trusts only the EKS Pod
  Identity service principal and constrains the request tags to this cluster
  ARN, `kube-system`, and `ebs-csi-controller-sa`.
- [`storageclass-splatform-gp3.yaml`](storageclass-splatform-gp3.yaml) defines
  encrypted `gp3` storage, `Retain`, and `WaitForFirstConsumer`. It does not set
  itself as the cluster default. With no `kmsKeyId`, EBS uses the verified
  regional default key `alias/aws/ebs`; no customer KMS key permissions are added.
- [`deny-ebs-outside-eu-central-1.json`](deny-ebs-outside-eu-central-1.json)
  adds an explicit role policy deny for all EC2 actions outside the target
  region, constraining the managed policy's effective EC2 region scope. It does
  not scope unrelated AWS services or the account as a whole.
- The PVC is in [`pvc-smoke-splatform-gp3.yaml`](pvc-smoke-splatform-gp3.yaml);
  the writer is in [`pod-smoke-writer-splatform-gp3.yaml`](pod-smoke-writer-splatform-gp3.yaml);
  a separate read-only reader is in
  [`pvc-smoke-reader-splatform-gp3.yaml`](pvc-smoke-reader-splatform-gp3.yaml).

The selected policy ARN is
`arn:aws:iam::aws:policy/AmazonEBSCSIDriverEKSClusterScopedPolicy`. AWS documents
that this policy limits EBS volume and snapshot management by matching
`ebs.csi.aws.com/cluster-name` resource tags to the Pod Identity
`eks-cluster-name` principal tag. It still grants conditional `ec2:DeleteVolume`
and `ec2:DeleteSnapshot` permissions for matching resources. The StorageClass
`Retain` policy protects the normal Kubernetes reclaim path; it does not remove
those IAM permissions or prevent a separately authorized/manual delete. The
separate inline policy explicitly denies all `ec2:*` requests when
`aws:RequestedRegion` is not `eu-central-1`. Attached to this dedicated role,
it constrains the managed policy's effective EC2 scope to Frankfurt; it does
not claim to scope unrelated AWS services or the account as a whole.

AWS's add-on metadata for the selected version recommends
`AmazonEBSCSIDriverPolicyV2`. This plan intentionally chooses the cluster-scoped
policy because AWS publishes it as a supported managed policy and all five
currently registered EC2 worker nodes were read-only verified to carry either
`eks:cluster-name=nonprod-euc1` or `eks:eks-cluster-name=nonprod-euc1`. AWS Pod
Identity supplies the `eks-cluster-name` session tag; the trust document also
binds the role to this cluster ARN, namespace, and service account. Recheck node
tags and the managed policy's default version immediately before applying. AWS
documents that the EKS add-on sets the driver's `--k8s-tag-cluster-id` option;
the selected add-on version is newer than the v1.58.0 threshold where the
driver adds the required cluster-name tag automatically.

## Single approval gate

This directory is the concrete change set for one approval covering the new IAM
role and managed policy attachment, EBS CSI add-on plus its Pod Identity
association, StorageClass, and bounded 1 GiB storage smoke test. The role has
conditional EBS delete permissions even though the class uses `Retain`; review
that specific security scope. The AWS CLI principal must have the required IAM
role creation/attachment, `iam:PassRole`, and EKS add-on permissions. Do not
apply any of these changes before that approval.

## CLI plan — review only, do not execute yet

These commands are a proposed sequence after approval. Every AWS command names
the profile explicitly and every Kubernetes command names the cluster context.
`create-addon` creates the EBS CSI add-on and its Pod Identity association
together; do not also create a duplicate standalone association. The plan
contains no update, delete, or replacement of an existing add-on because
discovery found none. Run AWS commands from the repository root so the trust
policy path resolves.

First, rerun read-only checks and inspect the trust document and policy version:

```sh
aws sts get-caller-identity \
  --profile 120736097561_betterix-AdministratorAccess

aws eks describe-cluster \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --name nonprod-euc1 \
  --query 'cluster.{name:name,arn:arn,version:version,status:status}'

aws eks list-addons \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1

kubectl --context nonprod-euc1 get nodes \
  -o custom-columns=NAME:.metadata.name,PROVIDER_ID:.spec.providerID
aws eks describe-cluster \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --name nonprod-euc1 --query cluster.endpoint --output text
kubectl --context nonprod-euc1 config view --minify -o jsonpath='{.clusters[0].cluster.server}'
aws ec2 describe-instances \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 \
  --filters 'Name=tag:eks:cluster-name,Values=nonprod-euc1' Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].{InstanceId:InstanceId,Tags:Tags[?Key==`eks:cluster-name`]}'
aws ec2 describe-instances \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 \
  --filters 'Name=tag:eks:eks-cluster-name,Values=nonprod-euc1' Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].{InstanceId:InstanceId,Tags:Tags[?Key==`eks:eks-cluster-name`]}'
kubectl --context nonprod-euc1 get storageclass splatform-gp3 --ignore-not-found
kubectl --context nonprod-euc1 get namespace splatform
kubectl --context nonprod-euc1 get pvc splatform-gp3-smoke -n splatform --ignore-not-found
kubectl --context nonprod-euc1 get pod splatform-gp3-smoke-writer -n splatform --ignore-not-found
kubectl --context nonprod-euc1 get pod splatform-gp3-smoke-reader -n splatform --ignore-not-found
kubectl --context nonprod-euc1 get csidriver ebs.csi.aws.com --ignore-not-found -o name
kubectl --context nonprod-euc1 get deployment,daemonset -A -o name | rg ebs-csi
kubectl --context nonprod-euc1 get pods -n kube-system -l app.kubernetes.io/name=eks-pod-identity-agent -o wide
kubectl --context nonprod-euc1 get storageclass -o custom-columns=NAME:.metadata.name,PROVISIONER:.provisioner
kubectl --context nonprod-euc1 get pv -o custom-columns=NAME:.metadata.name,DRIVER:.spec.csi.driver,CLAIM_NAMESPACE:.spec.claimRef.namespace,CLAIM:.spec.claimRef.name
kubectl --context nonprod-euc1 get pvc -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STORAGECLASS:.spec.storageClassName

aws eks describe-addon-versions \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --addon-name aws-ebs-csi-driver \
  --kubernetes-version 1.36 \
  --query "addons[0].addonVersions[?addonVersion=='v1.67.2-eksbuild.1']"

aws eks describe-addon-configuration \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --addon-name aws-ebs-csi-driver \
  --addon-version v1.67.2-eksbuild.1 --query podIdentityConfiguration

aws iam get-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --policy-arn arn:aws:iam::aws:policy/AmazonEBSCSIDriverEKSClusterScopedPolicy \
  --query 'Policy.{Arn:Arn,DefaultVersionId:DefaultVersionId,UpdateDate:UpdateDate}'

aws iam get-role \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller

aws iam get-policy-version \
  --profile 120736097561_betterix-AdministratorAccess \
  --policy-arn arn:aws:iam::aws:policy/AmazonEBSCSIDriverEKSClusterScopedPolicy \
  --version-id v2 --query PolicyVersion.Document

aws ec2 get-ebs-default-kms-key-id \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1
aws kms describe-key \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --key-id alias/aws/ebs \
  --query 'KeyMetadata.{Arn:Arn,KeyManager:KeyManager,KeyState:KeyState,Enabled:Enabled}'
```

The role check must return `NoSuchEntity`; if it exists, stop without changing
it. Confirm `GetEbsDefaultKmsKeyId` returns `alias/aws/ebs` and that
`DescribeKey` resolves that alias to the enabled AWS-managed key before
approval. Inspect the actual default policy JSON through IAM before approval;
AWS may update managed policy versions after this draft. If any EBS CSI
StorageClass, CSIDriver, controller workload, or EBS CSI PV exists, stop and
review the existing setup rather than adopting or altering it.

After approval, create the dedicated role, install the regional deny before
granting EBS permissions, then attach the selected AWS managed policy. Each
mutation is a stop-on-error boundary: if a command fails, stop and inspect the
resulting state instead of continuing. A role-name collision is a hard stop;
never reuse or modify that role.

```sh
aws iam create-role \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --description 'EBS CSI Pod Identity for nonprod-euc1 only' \
  --assume-role-policy-document file://deploy/eks/storage-prerequisites/pod-identity-trust.json

aws iam put-role-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --policy-name DenyEBSCSIOutsideEuCentral1 \
  --policy-document file://deploy/eks/storage-prerequisites/deny-ebs-outside-eu-central-1.json

aws iam attach-role-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --policy-arn arn:aws:iam::aws:policy/AmazonEBSCSIDriverEKSClusterScopedPolicy
```

Before creating the add-on, verify the deny is attached exactly and matches the
reviewed regional policy. Stop if the policy is absent or differs:

```sh
aws iam get-role-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --policy-name DenyEBSCSIOutsideEuCentral1
```

Before creating the add-on, verify that no association already exists for
exactly `kube-system/ebs-csi-controller-sa`. The following result must be an empty
list; otherwise stop without creating or changing the add-on or association:

```sh
aws eks list-pod-identity-associations \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --query "associations[?namespace=='kube-system' && serviceAccount=='ebs-csi-controller-sa']"
```

Then create the add-on pinned to the reviewed version and attach its Pod
Identity association to exactly `kube-system/ebs-csi-controller-sa`:

```sh
aws eks create-addon \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --addon-name aws-ebs-csi-driver \
  --addon-version v1.67.2-eksbuild.1 \
  --client-request-token splatform-nonprod-euc1-ebs-csi-v1 \
  --resolve-conflicts NONE \
  --namespace-config namespace=kube-system \
  --pod-identity-associations '[{"serviceAccount":"ebs-csi-controller-sa","roleArn":"arn:aws:iam::120736097561:role/nonprod-euc1-ebs-csi-controller"}]'
```

The client request token makes this create request idempotent. `NONE` ensures
the create fails rather than overwrites existing add-on configuration; rerun
discovery immediately before execution and proceed only while the add-on is
absent. The association is created as part of the request and must not also be
created separately. Its create input intentionally contains only
`serviceAccount` and `roleArn`; verify `disableSessionTags` is false afterward
rather than passing that output field as create input.

Finally, after the add-on reports `ACTIVE`, recheck all namespaces immediately
before creating the StorageClass. The following result must be empty; if any PVC
already references `splatform-gp3`, stop before creating the class because it
could provision that existing claim:

```sh
kubectl --context nonprod-euc1 get pvc -A \
  -o jsonpath='{range .items[?(@.spec.storageClassName=="splatform-gp3")]}{.metadata.namespace}{"/"}{.metadata.name}{"\n"}{end}'
```

Then create only the named StorageClass. This is absent-only; on any error stop
and inspect state. Do not use `apply` or replace a conflicting class:

```sh
kubectl --context nonprod-euc1 create \
  -f deploy/eks/storage-prerequisites/storageclass-splatform-gp3.yaml
```

Before provisioning, repeat the read-only preflight for the exact Pod Identity
association, agents, all StorageClasses, PVs, and all PVC claims. Stop if an
unexpected object or claim exists; do not broaden this change to handle existing
resources. Create the PVC alone, then inspect its returned UID, class, and size
before creating the writer. Each create is absent-only; a failed mutation is a
hard stop. Require one matching association with the expected add-on owner ARN,
role ARN, and `disableSessionTags: false`, plus all five agent pods Ready; stop
if these checks differ:

```sh
aws eks list-pod-identity-associations \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --query "associations[?namespace=='kube-system' && serviceAccount=='ebs-csi-controller-sa']"
aws eks describe-addon \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --addon-name aws-ebs-csi-driver --query addon.addonArn
aws eks describe-pod-identity-association \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --association-id <association-id-from-list> \
  --query 'association.{Namespace:namespace,ServiceAccount:serviceAccount,RoleArn:roleArn,OwnerArn:ownerArn,DisableSessionTags:disableSessionTags}'
kubectl --context nonprod-euc1 get pods -n kube-system -l app.kubernetes.io/name=eks-pod-identity-agent -o wide
kubectl --context nonprod-euc1 get storageclass -o custom-columns=NAME:.metadata.name,PROVISIONER:.provisioner
kubectl --context nonprod-euc1 get pv -o custom-columns=NAME:.metadata.name,DRIVER:.spec.csi.driver,CLAIM_NAMESPACE:.spec.claimRef.namespace,CLAIM:.spec.claimRef.name
kubectl --context nonprod-euc1 get pvc -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,STORAGECLASS:.spec.storageClassName
kubectl --context nonprod-euc1 create -f deploy/eks/storage-prerequisites/pvc-smoke-splatform-gp3.yaml -o yaml
kubectl --context nonprod-euc1 get pvc splatform-gp3-smoke -n splatform -o json
kubectl --context nonprod-euc1 create -f deploy/eks/storage-prerequisites/pod-smoke-writer-splatform-gp3.yaml -o yaml
```

The PVC requests 1 GiB of encrypted gp3. The writer creates its marker in
noclobber mode and fails rather than overwriting an existing marker. After the
writer succeeds, verify its UID and labels against its create response. Capture
the PVC's PV name and EBS volume handle before creating the reader. The reader
mounts the same claim read-only and must print the exact marker. Keep the PVC,
writer Pod, reader Pod, PV, and EBS volume after the test. The retained 1 GiB
volume is billable; the class remains non-default.

Create the reader only after the writer succeeds and the PV/volume handle have
been recorded. Stop if this absent-only create fails:

```sh
kubectl --context nonprod-euc1 wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/splatform-gp3-smoke-writer -n splatform --timeout=10m
kubectl --context nonprod-euc1 logs -n splatform pod/splatform-gp3-smoke-writer | rg -x 'splatform-gp3 smoke ok'
kubectl --context nonprod-euc1 get pod splatform-gp3-smoke-writer -n splatform \
  -o jsonpath='{.metadata.uid}{" "}{.metadata.labels.app\.kubernetes\.io/name}{" "}{.metadata.labels.app\.kubernetes\.io/role}{"\n"}'
kubectl --context nonprod-euc1 get pvc splatform-gp3-smoke -n splatform \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,CLASS:.spec.storageClassName,PHASE:.status.phase,PV:.spec.volumeName
kubectl --context nonprod-euc1 get pv \
  -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,VOLUME_ID:.spec.csi.volumeHandle
kubectl --context nonprod-euc1 create \
  -f deploy/eks/storage-prerequisites/pvc-smoke-reader-splatform-gp3.yaml
```

## Verification after the approved application

These checks are read-only:

```sh
aws eks describe-addon \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --addon-name aws-ebs-csi-driver \
  --query 'addon.{name:addonName,version:addonVersion,status:status}'

aws eks list-pod-identity-associations \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --query "associations[?namespace=='kube-system' && serviceAccount=='ebs-csi-controller-sa']"

aws eks describe-addon \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --addon-name aws-ebs-csi-driver --query addon.addonArn

aws eks describe-pod-identity-association \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --cluster-name nonprod-euc1 \
  --association-id <association-id-from-list> \
  --query 'association.{Namespace:namespace,ServiceAccount:serviceAccount,RoleArn:roleArn,OwnerArn:ownerArn,DisableSessionTags:disableSessionTags}'

aws iam get-role \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --query 'Role.AssumeRolePolicyDocument'

aws iam list-attached-role-policies \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller

aws iam get-role-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --role-name nonprod-euc1-ebs-csi-controller \
  --policy-name DenyEBSCSIOutsideEuCentral1

kubectl --context nonprod-euc1 get csidriver ebs.csi.aws.com
kubectl --context nonprod-euc1 get pods -n kube-system -o wide | rg 'ebs-csi-(controller|node)'
kubectl --context nonprod-euc1 get deployment,daemonset -n kube-system | rg ebs-csi
kubectl --context nonprod-euc1 get deployment ebs-csi-controller -n kube-system -o jsonpath='{.spec.template.spec.containers[?(@.name=="ebs-plugin")].args}{"\n"}'
kubectl --context nonprod-euc1 get storageclass splatform-gp3 -o yaml
kubectl --context nonprod-euc1 get pvc,pod -n splatform \
  -l app.kubernetes.io/name=splatform-gp3-smoke -o wide
kubectl --context nonprod-euc1 wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/splatform-gp3-smoke-writer -n splatform --timeout=10m
kubectl --context nonprod-euc1 logs -n splatform pod/splatform-gp3-smoke-writer | rg -x 'splatform-gp3 smoke ok'
kubectl --context nonprod-euc1 get pod splatform-gp3-smoke-writer -n splatform \
  -o jsonpath='{.metadata.uid}{" "}{.metadata.labels.app\.kubernetes\.io/name}{" "}{.metadata.labels.app\.kubernetes\.io/role}{"\n"}'
kubectl --context nonprod-euc1 get pvc splatform-gp3-smoke -n splatform \
  -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,CLASS:.spec.storageClassName,PHASE:.status.phase,PV:.spec.volumeName
kubectl --context nonprod-euc1 get pv \
  -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,VOLUME_ID:.spec.csi.volumeHandle
kubectl --context nonprod-euc1 wait --for=jsonpath='{.status.phase}'=Succeeded \
  pod/splatform-gp3-smoke-reader -n splatform --timeout=10m
kubectl --context nonprod-euc1 logs -n splatform pod/splatform-gp3-smoke-reader | rg -x 'splatform-gp3 smoke ok'
kubectl --context nonprod-euc1 get pv \
  -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,VOLUME_ID:.spec.csi.volumeHandle
```

Verify exactly one matching association, its `ownerArn` equals the EBS add-on
ARN (not the cluster ARN), its role ARN is the dedicated role, and
`disableSessionTags` is false (session
tags provide the cluster principal tag used by the managed policy). Verify the
add-on status/version, controller and node pods ready, controller args include
`--k8s-tag-cluster-id=nonprod-euc1`, the PVC `Bound`, and writer and reader
pods `Succeeded` with exact marker output. The reader mount is read-only and
uses the same PVC. Verify class fields match the manifest. Confirm the EBS
volume is encrypted with `KmsKeyId` equal to the verified regional default,
`gp3`, 1 GiB, and carries
`ebs.csi.aws.com/cluster-name=nonprod-euc1` and the driver's attach/detach
tag; confirm its exact key against the selected managed-policy v2 JSON and
driver version:

```sh
aws ec2 describe-volumes \
  --profile 120736097561_betterix-AdministratorAccess \
  --region eu-central-1 --volume-ids <volume-id-from-pv> \
  --query 'Volumes[].{VolumeId:VolumeId,Size:Size,Type:VolumeType,Encrypted:Encrypted,KmsKeyId:KmsKeyId,State:State,Tags:Tags}'
```


Before relying on the regional deny, use IAM policy simulation as a read-only
check: expect an EC2 action explicitly denied in another region. In
`eu-central-1`, this standalone deny policy has no matching deny (the simulator
will report implicit deny because this test policy contains no allow; the
managed policy supplies permissions):

```sh
aws iam simulate-custom-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --policy-input-list "$(cat deploy/eks/storage-prerequisites/deny-ebs-outside-eu-central-1.json)" \
  --action-names ec2:DescribeVolumes --resource-arns '*' \
  --context-entries '[{"ContextKeyName":"aws:RequestedRegion","ContextKeyValues":["us-east-1"],"ContextKeyType":"string"}]'
aws iam simulate-custom-policy \
  --profile 120736097561_betterix-AdministratorAccess \
  --policy-input-list "$(cat deploy/eks/storage-prerequisites/deny-ebs-outside-eu-central-1.json)" \
  --action-names ec2:DescribeVolumes --resource-arns '*' \
  --context-entries '[{"ContextKeyName":"aws:RequestedRegion","ContextKeyValues":["eu-central-1"],"ContextKeyType":"string"}]'
```

## Rollback and data safety

- If provisioning or driver health fails, stop workloads from creating new
  claims with `splatform-gp3`, then diagnose. Do not delete PVCs, PVs, EBS
  volumes, snapshots, or attachments as rollback.
- Keep every smoke resource: PVC, completed writer Pod, completed reader Pod,
  retained PV, EBS volume, and marker. This plan includes no test-resource
  deletion or cleanup.
- Keep the add-on and role available while any claims, PVs, or volume attachments
  might depend on them. Do not remove the add-on, Pod Identity association, or
  IAM policy as an automatic rollback step.
- `Retain` leaves released PVs for manual reclamation. Preserve the PV objects
  and underlying EBS volumes until an owner-approved recovery plan accounts for
  every claim and attachment.
- Before any later teardown, inventory all PVCs/PVs, `VolumeAttachment`
  objects, and tagged EBS volumes. This draft includes no destructive commands;
  any future teardown must be separately scoped so retained data is not lost.

## Official references

- [EKS Pod Identity role trust policy and request-tag conditions](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-role.html)
- [AWS managed `AmazonEBSCSIDriverEKSClusterScopedPolicy` (default version v2)](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonEBSCSIDriverEKSClusterScopedPolicy.html)
- [EKS IAM best practices: EBS CSI policy scoping and cluster tags](https://docs.aws.amazon.com/eks/latest/best-practices/identity-and-access-management.html)
- [EKS add-on IAM discovery and recommended policy](https://docs.aws.amazon.com/eks/latest/userguide/retreive-iam-info.html)
- [Create an EKS add-on Pod Identity association](https://docs.aws.amazon.com/eks/latest/userguide/update-addon-role.html)
- [EKS EBS CSI driver and StorageClass parameters](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)
- [Kubernetes StorageClass reclaim and binding behavior](https://kubernetes.io/docs/concepts/storage/storage-classes/)
